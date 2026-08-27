from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from .models import User, DoctorProfile, Attendance, Invoice, Patient, Appointment, Prescription
from django.db.models import Q
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone
from django.http import HttpResponse, FileResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from io import BytesIO
import stripe
from django.conf import settings
from django.shortcuts import redirect

# 1. Custom Login View
def custom_login(request):
    if request.method == 'POST':
        identifier = request.POST.get('login_id') 
        password = request.POST.get('password')
        user_obj = None

        try:
            # Logic: "Find a user where Username is X OR Email is X"
            user_obj = User.objects.get(Q(username=identifier) | Q(email=identifier))
        except User.DoesNotExist:
            # If no user matches either, user_obj stays None
            user_obj = None

        if user_obj is not None:
            user = authenticate(request, username=user_obj.username, password=password)
            if user is not None:
                login(request, user)
                if user.role == 'ADMIN' or user.is_superuser:
                    return redirect('admin_dashboard')
                elif user.role == 'RECEPTIONIST':
                    return redirect('reception_dashboard')
                elif user.role == 'DOCTOR':
                    return redirect('doctor_dashboard')
                elif user.role == 'PATIENT':
                    return redirect('patient_dashboard')
            else:
                messages.error(request, "Invalid Password")
            
        else:
            messages.error(request, "User not found (Check Username or Email)")
            
    return render(request, 'login.html')

# === ADMIN VIEWS ===

# 1. Admin Dashboard View
@login_required
def admin_dashboard(request):
    if request.user.role != 'ADMIN' and not request.user.is_superuser:
        return redirect('custom_login')

    today = timezone.now().date()

    # 1. Calculate Total Income Today
    total_income = Invoice.objects.filter(date=today, is_paid=True).aggregate(Sum('amount'))['amount__sum'] or 0
    print("total_income",type(total_income))

    # 2. Count Active Doctors (Present today)
    active_docs = Attendance.objects.filter(date=today, is_present=True).count()
    

    context = {
        'total_income': total_income,
        'active_appointments': 0, # Placeholder until we build Patient flow
        'doctors_count': DoctorProfile.objects.count(),
        'active_docs': active_docs
    }
    return render(request, 'admin/dashboard.html', context)

# 2. Manage Doctors (Add Doctor)
@login_required
def add_doctor(request):
    
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        dept = request.POST.get('department')
        fee = request.POST.get('fee')

        # Create User
        try:
            new_user = User.objects.create_user(username=name, email=email, password=password)
            new_user.role = 'DOCTOR'
            new_user.save()

            # Create Profile
            DoctorProfile.objects.create(user=new_user, department=dept, consultation_fee=fee)
            messages.success(request, "Doctor Added Successfully")
            return redirect('admin_dashboard')
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, 'admin/add_doctor.html')

# 3. View Reports
@login_required
def view_reports(request):
    if request.user.role != 'ADMIN' and not request.user.is_superuser:
        return redirect('custom_login')
        
    today = timezone.now().date()

    # Fetch Attendance for Today
    attendance_logs = Attendance.objects.filter(date=today)
    

    # Fetch Revenue Breakdown
    cash_total = Invoice.objects.filter(date=today, mode='CASH', is_paid=True).aggregate(Sum('amount'))['amount__sum'] or 0
    online_total = Invoice.objects.filter(date=today, mode='ONLINE', is_paid=True).aggregate(Sum('amount'))['amount__sum'] or 0

    context = {
        'attendance_logs': attendance_logs,
        'cash_total': cash_total,
        'online_total': online_total,
        'today': today
    }
    return render(request, 'admin/reports.html', context)

@login_required
def add_staff(request):
    # Security: Only Admin can add staff
    if request.user.role != 'ADMIN' and not request.user.is_superuser:
        return redirect('custom_login')

    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        try:
            # 1. Create the User
            new_user = User.objects.create_user(username=name, email=email, password=password)
            
            # 2. Assign Role
            new_user.role = 'RECEPTIONIST'
            new_user.save()
            
            messages.success(request, "Receptionist Added Successfully")
            return redirect('admin_dashboard')
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return render(request, 'admin/add_staff.html')


# === RECEPTIONIST VIEWS ===
@login_required
def reception_dashboard(request):
    # Role Check
    if request.user.role != 'RECEPTIONIST' and not request.user.is_superuser:
        return redirect('custom_login')
    
    today = timezone.now().date()

    # 1. Today's Appointments
    todays_appointments = Appointment.objects.filter(date=today).order_by('time_slot')

    # 2. Pending Bills (Unpaid)
    pending_invoices = Invoice.objects.filter(is_paid=False)

    query = request.GET.get('q') # Get the search term from the URL
    
    if query:
        # Search Pending Invoices by Patient Name OR Phone Number
        pending_invoices = Invoice.objects.filter(
            Q(patient__name__icontains=query) | Q(patient__phone__icontains=query),
            is_paid=False
        )
    else:
        # If no search, show all pending bills
        pending_invoices = Invoice.objects.filter(is_paid=False)

    context = {
        'appointments': todays_appointments,
        'invoices': pending_invoices,
        'today': today
    }
    return render(request, 'reception/dashboard.html', context)

@login_required
def new_appointment(request):
    doctors = DoctorProfile.objects.all()
    
    if request.method == 'POST':
        phone = request.POST.get('phone')
        
        # Step 1: Find or Create Patient
        patient = Patient.objects.filter(phone=phone).first()
        if not patient:
            # Create new patient
            name = request.POST.get('name')
            age = request.POST.get('age')
            gender = request.POST.get('gender')
            patient = Patient.objects.create(name=name, phone=phone, age=age, gender=gender)
        
        # Step 2: Book Appointment
        doc_id = request.POST.get('doctor')
        date = request.POST.get('date')
        time = request.POST.get('time')
        
        doctor = DoctorProfile.objects.get(id=doc_id)
        
        # Create Appointment
        Appointment.objects.create(doctor=doctor, patient=patient, date=date, time_slot=time, status='SCHEDULED')
        
        messages.success(request, f"Appointment booked for {patient.name}")
        return redirect('reception_dashboard')

    return render(request, 'reception/new_appointment.html', {'doctors': doctors})

@login_required
def mark_arrived(request, appointment_id):
    # Workflow Step 4: Patient Arrives
    appt = Appointment.objects.get(id=appointment_id)
    appt.status = 'WAITING' # Put in Queue
    appt.save()
    messages.success(request, f"{appt.patient.name} marked as Waiting.")
    return redirect('reception_dashboard')

@login_required
def mark_paid(request, invoice_id):
    # Workflow Step 5: Collect Cash
    inv = Invoice.objects.get(id=invoice_id)
    inv.is_paid = True
    inv.mode = 'CASH'
    inv.save()
    messages.success(request, f"Received ₹{inv.amount} Cash from {inv.patient.name}.")
    return redirect('reception_dashboard')

# === DOCTOR VIEWS ===
@login_required
def doctor_dashboard(request):
    # Role Check
    print(request)
    if request.user.role != 'DOCTOR':
        return redirect('custom_login')
    
    # Get the Doctor Profile linked to this user
    try:
        doctor_profile = request.user.doctor_profile
    except DoctorProfile.DoesNotExist:
        messages.error(request, "Doctor Profile not found.")
        return redirect('custom_login')

    today = timezone.now().date()
    
    # Fetch appointments for THIS doctor only, for TODAY
    appointments = Appointment.objects.filter(
        doctor=doctor_profile, 
        date=today
    ).order_by('time_slot')

    return render(request, 'doctor/dashboard.html', {'appointments': appointments})

@login_required
def consultation(request, appointment_id):
    appointment = Appointment.objects.get(id=appointment_id)
    
    if request.method == 'POST':
        # Step 3 & 4: Save Data & Trigger Automation
        
        # A. Save Prescription
        diagnosis = request.POST.get('diagnosis')
        medicine = request.POST.get('medicine')
        notes = request.POST.get('notes')
        
        Prescription.objects.create(
            appointment=appointment,
            diagnosis=diagnosis,
            medicine=medicine,
            notes=notes,
            is_locked=True # Step 4: PDF is locked initially
        )
        
        # B. Mark Completed
        appointment.status = 'COMPLETED'
        appointment.save()
        
        # C. Generate Invoice (Step 4 Automation)
        Invoice.objects.create(
            appointment=appointment,
            patient=appointment.patient,
            amount=appointment.doctor.consultation_fee, # Auto-fetch fee
            mode='CASH', # Default
            is_paid=False # Pending
        )
        
        messages.success(request, "Consultation Complete. Invoice Generated.")
        return redirect('doctor_dashboard')

    return render(request, 'doctor/consult.html', {'appt': appointment})


# === PATIENT VIEWS ===
def patient_register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        name = request.POST.get('name')
        phone = request.POST.get('phone') 
        email = request.POST.get('email')
        password = request.POST.get('password')
        age = request.POST.get('age')
        gender = request.POST.get('gender')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return redirect('patient_register')
            
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered.")
            return redirect('patient_register')

        if Patient.objects.filter(phone=phone).exists():
            messages.error(request, "Phone number already registered.")
            return redirect('patient_register')

        try:
            user = User.objects.create_user(username=username, email=email,password=password)
            user.role = 'PATIENT'
            user.save()
            
            Patient.objects.create(user=user, name=name, phone=phone, age=age, gender=gender)
            
            messages.success(request, "Account created! Please login.")
            return redirect('custom_login')
        except Exception as e:
            messages.error(request, f"Error: {e}")
            return redirect('patient_register')

    return render(request, 'patient/register.html')

@login_required
def patient_dashboard(request):
    if request.user.role != 'PATIENT':
        return redirect('custom_login')
    return render(request, 'patient/dashboard.html')

@login_required
def book_appointment(request):
    # Step 2: Booking
    doctors = DoctorProfile.objects.all()
    
    if request.method == 'POST':
        doc_id = request.POST.get('doctor')
        date = request.POST.get('date')
        time = request.POST.get('time')
        
        doctor = DoctorProfile.objects.get(id=doc_id)
        patient = request.user.patient_profile # Link to logged-in user
        
        # Create Appointment
        Appointment.objects.create(
            doctor=doctor, 
            patient=patient, 
            date=date, 
            time_slot=time, 
            status='SCHEDULED'
        )
        messages.success(request, "Booking Confirmed! Token #12 (Mock)")
        return redirect('patient_dashboard')

    return render(request, 'patient/book_appointment.html', {'doctors': doctors})

@login_required
def my_bills(request):
    # Step 4: Post-Visit Payment
    patient = request.user.patient_profile
    invoices = Invoice.objects.filter(patient=patient)
    
    return render(request, 'patient/my_bills.html', {'invoices': invoices})

def render_to_pdf(template_src, context_dict={}):
    """Helper: Renders HTML to a BytesIO object (in-memory file)"""
    template = get_template(template_src)
    html  = template.render(context_dict)
    
    # Create an in-memory buffer
    buffer = BytesIO()
    
    # Write PDF to the buffer
    pisa_status = pisa.CreatePDF(html, dest=buffer)
    
    if pisa_status.err:
        return None
    
    # IMPORTANT: Move the cursor to the beginning of the buffer so we can read it
    buffer.seek(0)
    return buffer

@login_required
def download_invoice_pdf(request, invoice_id):
    """View to generate the specific invoice PDF"""
    try:
        invoice = Invoice.objects.get(id=invoice_id, patient=request.user.patient_profile)
        
        context = {
            'invoice': invoice,
            'today': timezone.now().date(),
        }
        
        # Get the raw PDF content (file-like object)
        pdf_file = render_to_pdf('patient/invoice_pdf.html', context)
        
        if pdf_file:
            return FileResponse(pdf_file, as_attachment=True, filename=f'Invoice_{invoice.id}.pdf')
            
        return HttpResponse("Error Generating PDF", status=400)
        
    except Invoice.DoesNotExist:
        return HttpResponse("Invoice not found", status=404)
    
#payments
stripe.api_key = settings.STRIPE_SECRET_KEY

# 1. Start Payment (Patient clicks "Pay Online")
@login_required
def create_checkout_session(request, invoice_id):
    # 0. Initialize variables safely to prevent "UnboundLocalError"
    is_staff = False
    is_patient = False

    try:
        # 1. SAFER CHECKS
        # Check if user is a patient (using filter exists is safer than hasattr)
        is_patient = Patient.objects.filter(user=request.user).exists()
        
        # FIX: 'role' is a string, so we use 'in' list, NOT .filter()
        # We also use getattr() to avoid crashes if 'role' field is missing on the user model
        user_role = getattr(request.user, 'role', '')
        is_staff = user_role in ['RECEPTIONIST', 'DOCTOR', 'ADMIN'] or request.user.is_superuser
        
        # 2. GET THE INVOICE
        if is_patient:
            # Patient logic (Own bills only)
            # We get the profile safely now that we know it exists
            patient_profile = Patient.objects.get(user=request.user)
            invoice = Invoice.objects.get(id=invoice_id, patient=patient_profile)
            cancel_url = '/patient/my-bills/'
            
        elif is_staff:
            # Staff logic (Any bill)
            invoice = Invoice.objects.get(id=invoice_id)
            cancel_url = '/dashboard/reception/' 
            
        else:
            return HttpResponse("Unauthorized Access", status=403)
            
        # 3. STRIPE LOGIC
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'inr',
                    'product_data': {
                        'name': f"Invoice #{invoice.id} - {invoice.patient.name}",
                    },
                    'unit_amount': int(invoice.amount * 100),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=request.build_absolute_uri(f'/payment-success/{invoice.id}/'),
            cancel_url=request.build_absolute_uri(cancel_url),
        )
        return redirect(session.url, code=303)
        
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")
        # Now this will work because is_staff was defined at the very top
        if is_staff:
            return redirect('reception_dashboard')
        return redirect('my_bills')

@login_required
def payment_success(request, invoice_id):
    try:
        # 1. Update the Invoice
        invoice = Invoice.objects.get(id=invoice_id)
        invoice.is_paid = True
        invoice.mode = 'Online'
        invoice.save()
        
        messages.success(request, "Payment Successful! Receipt generated.")

        # 2. SMART REDIRECT
        
        # CHECK: Is this user a Patient?
        if Patient.objects.filter(user=request.user).exists():
            return redirect('my_bills')
            
        # CHECK: Is this user Staff (Admin/Reception)?
        # We use getattr to safely get role, defaulting to empty string if missing
        user_role = getattr(request.user, 'role', '')
        if request.user.is_superuser or user_role in ['RECEPTIONIST', 'DOCTOR', 'ADMIN']:
            return redirect('reception_dashboard')
            
        # Fallback
        return redirect('custom_login')

    except Invoice.DoesNotExist:
        messages.error(request, "Error: Invoice not found.")
        return redirect('custom_login')
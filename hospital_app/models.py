from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):
    # Roles to distinguish user types
    ROLE_CHOICES = (
        ('ADMIN', 'Admin'),
        ('DOCTOR', 'Doctor'),
        ('RECEPTIONIST', 'Receptionist'),
        ('PATIENT', 'Patient'),
    )
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='ADMIN')

    # Add common fields if needed, e.g., phone_number
    phone_number = models.CharField(max_length=15, blank=True, null=True)

class DoctorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    department = models.CharField(max_length=100)
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=500.00)
    
    def __str__(self):
        return f"Dr. {self.user.username} - {self.department}"

class Attendance(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    in_time = models.TimeField(null=True, blank=True)
    out_time = models.TimeField(null=True, blank=True)
    is_present = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.date}"

class Patient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile', null=True, blank=True)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, unique=True) # Phone is unique ID
    age = models.IntegerField()
    gender = models.CharField(max_length=10, choices=[('M','Male'), ('F','Female'), ('O','Other')])
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.phone})"

class Appointment(models.Model):
    STATUS_CHOICES = (
        ('SCHEDULED', 'Scheduled'), # Just booked
        ('WAITING', 'Waiting'),     # Patient is in the hospital (Queue)
        ('VISITING', 'Visiting'),   # Inside doctor's cabin
        ('COMPLETED', 'Completed'), # Done
        ('CANCELLED', 'Cancelled'),
    )

    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='appointments')
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    date = models.DateField()
    time_slot = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    
    # Simple token number for the day
    token_number = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.patient.name} - {self.doctor} - {self.status}"

class Invoice(models.Model):
    PAYMENT_MODES = (('CASH', 'Cash'), ('ONLINE', 'Online'))
    
    # Link to Appointment (so we know which visit this bill is for)
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, null=True, blank=True)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, null=True, blank=True) # Fallback link
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    mode = models.CharField(max_length=10, choices=PAYMENT_MODES, default='CASH')
    date = models.DateField(auto_now_add=True)
    is_paid = models.BooleanField(default=False)

    def __str__(self):
        return f"Inv #{self.id} - ₹{self.amount}"

class Prescription(models.Model):
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name='prescription')
    diagnosis = models.CharField(max_length=200)
    medicine = models.TextField(help_text="Medicine name and dosage")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # The flag mentioned in Step 4 (PDF Locked until payment)
    is_locked = models.BooleanField(default=True)

    def __str__(self):
        return f"Rx for {self.appointment.patient.name}"
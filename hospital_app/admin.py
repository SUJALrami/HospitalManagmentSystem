from django.contrib import admin
from .models import User, DoctorProfile, Attendance, Invoice

admin.site.register(User)
admin.site.register(DoctorProfile)
admin.site.register(Attendance)
admin.site.register(Invoice)
from django.urls import path,include

urlpatterns = [    
    # Custom URLs
    path('', include('hospital_app.urls')),
]
from django.urls import path
from . import views
from .views import login_statistics


urlpatterns = [
    path("register/", views.register_user, name="register"),
    path("login/", views.authenticate_user, name="login"),
    path("login-multiframe/", views.authenticate_user_multiframe, name="login_multiframe"),
    path("stats/",views.login_statistics, name="login_statistics"),
    path("far/", views.far_statistics, name="far_statistics"),
    path("anomaly/", views.anomaly_statistics, name="anomaly_statistics"), 
    path("report/", views.generate_report, name="generate_report"),
]
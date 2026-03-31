from django.urls import path
from . import views
from .views import login_statistics


urlpatterns = [
    path("register/", views.register_user, name="register"),
    path("login/", views.authenticate_user, name="login"),
    path("login-multiframe/", views.authenticate_user_multiframe, name="login_multiframe"),
    path("stats/", login_statistics)
]
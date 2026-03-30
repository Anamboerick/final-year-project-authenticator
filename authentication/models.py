from django.db import models

class UserProfile(models.Model):
    username = models.CharField(max_length=100, unique=True)
    face_encoding = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username


class LoginAttempt(models.Model):
    username = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)

    status = models.CharField(max_length=20)
    average_distance = models.FloatField(null=True, blank=True)
    valid_frames = models.IntegerField(default=0)

    liveness_passed = models.BooleanField(default=False)
    attempt_count =models.IntegerField(default=1)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
     return f"{self.username} - {self.status} - {self.timestamp}"

    

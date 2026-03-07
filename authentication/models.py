from django.db import models

class UserProfile(models.Model):
    username = models.CharField(max_length=100, unique=True)
    face_encoding = models.BinaryField()  # store encoded face
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username



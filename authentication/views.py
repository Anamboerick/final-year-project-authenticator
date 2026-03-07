import face_recognition
import pickle
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import UserProfile

@api_view(["POST"])
def register_user(request):
    username = request.data.get("username")
    image = request.FILES.get("image")

    if not username:
        return Response({"error": "Username required"}, status=400)

    if not image:
        return Response({"error": "Image required"}, status=400)

    img = face_recognition.load_image_file(image.file)
    encodings = face_recognition.face_encodings(img)

    if not encodings:
        return Response({"error": "No face detected"}, status=400)

    encoding = pickle.dumps(encodings[0])

    # update if exists, else create (avoids duplicate username crash)
    UserProfile.objects.update_or_create(
        username=username,
        defaults={"face_encoding": encoding},
    )

    return Response({"message": "User registered successfully"})

@api_view(["POST"])
def authenticate_user(request):
    username = request.data.get("username")
    image = request.FILES.get("image")

    if not username:
        return Response({"error": "Username required"}, status=400)

    if not image:
        return Response({"error": "Image required"}, status=400)

    try:
        user = UserProfile.objects.get(username=username)
    except UserProfile.DoesNotExist:
        return Response({"error": "User not found"}, status=404)

    img = face_recognition.load_image_file(image.file)
    encodings = face_recognition.face_encodings(img)

    if not encodings:
        return Response({"error": "No face detected"}, status=400)

    stored_encoding = pickle.loads(user.face_encoding)
    match = face_recognition.compare_faces([stored_encoding], encodings[0])

    return Response({"status": "Access Granted" if match[0] else "Access Denied"})
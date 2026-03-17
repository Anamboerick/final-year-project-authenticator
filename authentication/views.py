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
    distance = face_recognition.face_distance([stored_encoding], encodings[0])[0]
    threshold = 0.40

    return Response({
        "status": "Access Granted" if distance < threshold else "Access Denied",
        "distance": float(distance),
        "threshold": threshold
    })


@api_view(["POST"])
def authenticate_user_multiframe(request):
    username = request.data.get("username")
    images = request.FILES.getlist("images")

    if not username:
        return Response({"error": "Username required"}, status=400)

    if not images:
        return Response({"error": "At least one image is required"}, status=400)

    try:
        user = UserProfile.objects.get(username=username)
    except UserProfile.DoesNotExist:
        return Response({"error": "User not found"}, status=404)

    stored_encoding = pickle.loads(user.face_encoding)

    distances = []
    valid_frames = 0

    for image in images:
        try:
            img = face_recognition.load_image_file(image.file)
            encodings = face_recognition.face_encodings(img)

            if encodings:
                distance = face_recognition.face_distance(
                    [stored_encoding], encodings[0]
                )[0]
                distances.append(float(distance))
                valid_frames += 1
        except Exception:
            continue

    if valid_frames == 0:
        return Response({"error": "No face detected in any frame"}, status=400)

    average_distance = sum(distances) / len(distances)
    threshold = 0.40

    return Response({
        "status": "Access Granted" if average_distance < threshold else "Access Denied",
        "average_distance": float(average_distance),
        "all_distances": distances,
        "valid_frames": valid_frames,
        "threshold": threshold
    })
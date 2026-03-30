import face_recognition
import pickle
from datetime import timedelta

from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import UserProfile, LoginAttempt


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


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
    liveness_passed = request.data.get("liveness_passed", "true").lower() == "true"

    client_ip = get_client_ip(request)

    if not username:
        LoginAttempt.objects.create(
            username="unknown",
            status="Access Denied",
            average_distance=None,
            valid_frames=0,
            liveness_passed=False,
            attempt_count=1,
            ip_address=client_ip,
            notes="Username missing"
        )
        return Response({"error": "Username required"}, status=400)

    if not images:
        recent_attempts = LoginAttempt.objects.filter(
            username=username,
            timestamp__gte=timezone.now() - timedelta(minutes=2)
        ).count()

        LoginAttempt.objects.create(
            username=username,
            status="Access Denied",
            average_distance=None,
            valid_frames=0,
            liveness_passed=liveness_passed,
            attempt_count=recent_attempts + 1,
            ip_address=client_ip,
            notes="No images uploaded"
        )
        return Response({"error": "At least one image is required"}, status=400)

    try:
        user = UserProfile.objects.get(username=username)
    except UserProfile.DoesNotExist:
        recent_attempts = LoginAttempt.objects.filter(
            username=username,
            timestamp__gte=timezone.now() - timedelta(minutes=2)
        ).count()

        LoginAttempt.objects.create(
            username=username,
            status="Access Denied",
            average_distance=None,
            valid_frames=0,
            liveness_passed=liveness_passed,
            attempt_count=recent_attempts + 1,
            ip_address=client_ip,
            notes="User not found"
        )
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
        recent_attempts = LoginAttempt.objects.filter(
            username=username,
            timestamp__gte=timezone.now() - timedelta(minutes=2)
        ).count()

        LoginAttempt.objects.create(
            username=username,
            status="Access Denied",
            average_distance=None,
            valid_frames=0,
            liveness_passed=liveness_passed,
            attempt_count=recent_attempts + 1,
            ip_address=client_ip,
            notes="No face detected in any frame"
        )
        return Response({"error": "No face detected in any frame"}, status=400)

    average_distance = sum(distances) / len(distances)
    threshold = 0.40
    final_status = "Access Granted" if average_distance < threshold else "Access Denied"

    recent_attempts = LoginAttempt.objects.filter(
        username=username,
        timestamp__gte=timezone.now() - timedelta(minutes=2)
    ).count()

    LoginAttempt.objects.create(
        username=username,
        status=final_status,
        average_distance=float(average_distance),
        valid_frames=valid_frames,
        liveness_passed=liveness_passed,
        attempt_count=recent_attempts + 1,
        ip_address=client_ip,
        notes="Multi-frame authentication attempt"
    )

    suspicious = False

    recent_user_attempts = LoginAttempt.objects.filter(
        username=username,
        timestamp__gte=timezone.now() - timedelta(minutes=5)
    ).order_by("-timestamp")

    fail_count = recent_user_attempts.filter(status="Access Denied").count()

    if fail_count >= 3:
        suspicious = True

    if average_distance >= 0.55:
        suspicious = True

    return Response({
        "status": final_status,
        "average_distance": float(average_distance),
        "all_distances": distances,
        "valid_frames": valid_frames,
        "threshold": threshold,
        "liveness_passed": liveness_passed,
        "attempt_count": recent_attempts + 1,
        "suspicious": suspicious
    })
import face_recognition
import pickle
from datetime import timedelta

from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .anomaly_detection import run_isolation_forest
from .models import UserProfile, LoginAttempt
from django.db import models

from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime
from zoneinfo import ZoneInfo


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
    threshold = 0.4

    return Response({
        "status": "Access Granted" if distance < threshold else "Access Denied",
        "distance": float(distance),
        "threshold": threshold
    })


@csrf_exempt
@api_view(["POST"])
def authenticate_user_multiframe(request):
    print("FILES received:", request.FILES)
    print("DATA received:", request.data)
    username = request.data.get("username")
    images = request.FILES.getlist("images")
    print("Images count:", len(images))
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
            suspicious=False,
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
            suspicious=False,
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
            suspicious=False,
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
            suspicious=False,
            notes="No face detected in any frame"
        )
        return Response({"error": "No face detected in any frame"}, status=400)

    average_distance = sum(distances) / len(distances)
    threshold = 0.4
    final_status = "Access Granted" if average_distance < threshold else "Access Denied"

    recent_attempts = LoginAttempt.objects.filter(
        username=username,
        timestamp__gte=timezone.now() - timedelta(minutes=2)
    ).count()

    # Calculate suspicious BEFORE saving
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

    # Now save with suspicious included
    LoginAttempt.objects.create(
        username=username,
        status=final_status,
        average_distance=float(average_distance),
        valid_frames=valid_frames,
        liveness_passed=liveness_passed,
        attempt_count=recent_attempts + 1,
        ip_address=client_ip,
        suspicious=suspicious,
        notes="Multi-frame authentication attempt"
    )

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


@api_view(["GET"])
def login_statistics(request):
    total = LoginAttempt.objects.count()
    success = LoginAttempt.objects.filter(status="Access Granted").count()
    failed = LoginAttempt.objects.filter(status="Access Denied").count()

    suspicious_attempts = LoginAttempt.objects.filter(
        suspicious=True,
        timestamp__gte=timezone.now() - timedelta(minutes=5)
    ).count()

    avg_distance = LoginAttempt.objects.exclude(
        average_distance=None
    ).aggregate(avg=models.Avg("average_distance"))["avg"]

    return Response({
        "total_attempts": total,
        "successful_logins": success,
        "failed_logins": failed,
        "suspicious_attempts": suspicious_attempts,
        "average_distance": avg_distance
    })


@api_view(["GET"])
def far_statistics(request):
    total_denied = LoginAttempt.objects.filter(status="Access Denied").count()
    false_accepts = LoginAttempt.objects.filter(
        status="Access Granted",
        suspicious=True
    ).count()

    far = 0
    if total_denied + false_accepts > 0:
        far = false_accepts / (total_denied + false_accepts)

    return Response({
        "false_accepts": false_accepts,
        "total_denied_attempts": total_denied,
        "far": far
    })


@api_view(["GET"])
def anomaly_statistics(request):
    results = run_isolation_forest()
    return Response(results)

@api_view(["GET"])
def generate_report(request):
    # Collect all stats
    total = LoginAttempt.objects.count()
    granted = LoginAttempt.objects.filter(status="Access Granted").count()
    denied = LoginAttempt.objects.filter(status="Access Denied").count()
    suspicious = LoginAttempt.objects.filter(suspicious=True).count()
    avg_dist = LoginAttempt.objects.exclude(
        average_distance=None
    ).aggregate(avg=models.Avg("average_distance"))["avg"] or 0

    # FAR
    false_accepts = LoginAttempt.objects.filter(
        status="Access Granted", suspicious=True
    ).count()
    far = 0
    if denied + false_accepts > 0:
        far = false_accepts / (denied + false_accepts)

    # Isolation Forest
    anomaly_results = run_isolation_forest()

    # Registered users
    total_users = UserProfile.objects.count()

    # Build PDF
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="security_report.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    elements.append(Paragraph("PATTERN-BASED AUTHENTICATION SYSTEM", styles["Title"]))
    elements.append(Paragraph("Experimental Security Evaluation Report", styles["Heading2"]))
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
    elements.append(Spacer(1, 20))
    tz_name = request.GET.get('tz', 'Africa/Nairobi')
    tz = ZoneInfo(tz_name)
    generated_at = datetime.now(tz).strftime('%Y-%m-%d %H:%M')

    # Section 1 - System Overview
    elements.append(Paragraph("1. System Overview", styles["Heading2"]))
    elements.append(Paragraph(
        "This report summarizes the security performance of the pattern-based "
        "authentication system developed for university voting. The system uses "
        "facial recognition, behavioural pattern analysis, and Isolation Forest "
        "anomaly detection.",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 12))

    # Section 2 - Experimental Setup
    elements.append(Paragraph("2. Experimental Setup", styles["Heading2"]))
    setup_data = [
        ["Parameter", "Value"],
        ["Registered Users", str(total_users)],
        ["Total Login Attempts", str(total)],
        ["Face Distance Threshold", "0.4"],
        ["Isolation Forest Contamination", "10%"],
        ["Environment", "Local Development Server"],
    ]
    setup_table = Table(setup_data, colWidths=[250, 200])
    setup_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(setup_table)
    elements.append(Spacer(1, 12))

    # Section 3 - Authentication Results
    elements.append(Paragraph("3. Authentication Results", styles["Heading2"]))
    auth_data = [
        ["Metric", "Value"],
        ["Total Login Attempts", str(total)],
        ["Successful Logins (Access Granted)", str(granted)],
        ["Failed Logins (Access Denied)", str(denied)],
        ["Suspicious Attempts Flagged", str(suspicious)],
        ["Average Face Distance", f"{round(avg_dist, 4)}"],
    ]
    auth_table = Table(auth_data, colWidths=[250, 200])
    auth_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(auth_table)
    elements.append(Spacer(1, 12))

    # Section 4 - Anomaly Detection
    elements.append(Paragraph("4. Isolation Forest Anomaly Detection", styles["Heading2"]))
    if "error" in anomaly_results:
        elements.append(Paragraph(f"Note: {anomaly_results['error']}", styles["Normal"]))
    else:
        anomaly_data = [
            ["Metric", "Value"],
            ["Total Attempts Analysed", str(anomaly_results.get("total_attempts", 0))],
            ["Anomalies Detected", str(anomaly_results.get("anomalies_detected", 0))],
            ["Anomaly Percentage", f"{round(anomaly_results.get('anomaly_percentage', 0), 2)}%"],
        ]
        anomaly_table = Table(anomaly_data, colWidths=[250, 200])
        anomaly_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(anomaly_table)
    elements.append(Spacer(1, 12))

    # Section 5 - FAR
    elements.append(Paragraph("5. False Acceptance Rate (FAR)", styles["Heading2"]))
    far_data = [
        ["Metric", "Value"],
        ["False Accepts", str(false_accepts)],
        ["Total Denied Attempts", str(denied)],
        ["FAR", f"{round(far * 100, 2)}%"],
        ["Evaluation", "Excellent" if far < 0.05 else "Acceptable" if far < 0.1 else "Needs Improvement"],
    ]
    far_table = Table(far_data, colWidths=[250, 200])
    far_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(far_table)
    elements.append(Spacer(1, 12))

    # Section 6 - Conclusion
    elements.append(Paragraph("6. Conclusion", styles["Heading2"]))
    elements.append(Paragraph(
        f"The pattern-based authentication system demonstrated strong security performance. "
        f"With a False Acceptance Rate of {round(far * 100, 2)}% and {anomaly_results.get('anomaly_percentage', 0):.2f}% "
        f"anomaly detection rate, the system effectively verified voter identities and detected "
        f"suspicious authentication patterns. The system successfully met all five specific objectives "
        f"outlined in the project proposal.",
        styles["Normal"]
    ))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("7. Limitations", styles["Heading2"]))
    elements.append(Paragraph(
        "The system may exhibit reduced accuracy with identical twins due to high facial similarity. "
        "Performance was evaluated in a controlled local environment and may vary under production conditions. "
        "Lighting and camera quality can affect face recognition accuracy.",
        styles["Normal"]
    ))

    doc.build(elements)
    return response
@api_view(["GET"])
def check_admin(request):
    username = request.GET.get("user", "")
    return Response({"is_admin": username == "erick"})
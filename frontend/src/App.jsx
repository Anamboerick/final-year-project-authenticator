import React, { useRef, useState, useEffect } from "react";

export default function ReactFaceAuthFrontend() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const faceMeshRef = useRef(null);
  const detectionLoopRef = useRef(false);
  const verifyingRef = useRef(false);
  const blinkDetectedRef = useRef(false);
  const eyesClosedFramesRef = useRef(0);
  const latestFaceDataRef = useRef({ faceDetected: false, centered: false, eyeRatio: null });

  const [username, setUsername] = useState("");
  const [cameraStarted, setCameraStarted] = useState(false);
  const [faceGuideColor, setFaceGuideColor] = useState("red");
  const [instruction, setInstruction] = useState("Start camera and align your face to begin.");
  const [progress, setProgress] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [authStatus, setAuthStatus] = useState(null);

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const dist = (a, b) => Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2);
  const eyeAspectRatio = (upper, lower, left, right) =>
    dist(upper, lower) / dist(left, right);

  useEffect(() => {
    const script = document.createElement("script");
    script.src = "https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/face_mesh.js";
    script.onload = () => {
      const mesh = new window.FaceMesh({
        locateFile: (file) =>
          `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`,
      });
      mesh.setOptions({
        maxNumFaces: 1,
        refineLandmarks: true,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5,
      });
      mesh.onResults((results) => {
        latestFaceDataRef.current = { faceDetected: false, centered: false, eyeRatio: null };
        if (!results.multiFaceLandmarks || results.multiFaceLandmarks.length === 0) {
          setFaceGuideColor("red");
          return;
        }
        const face = results.multiFaceLandmarks[0];
        const leftEAR = eyeAspectRatio(face[159], face[145], face[33], face[133]);
        const rightEAR = eyeAspectRatio(face[386], face[374], face[362], face[263]);
        const avgEAR = (leftEAR + rightEAR) / 2;
        const nose = face[1];
        const centered = nose.x > 0.4 && nose.x < 0.6 && nose.y > 0.3 && nose.y < 0.7;
        latestFaceDataRef.current = { faceDetected: true, centered, eyeRatio: avgEAR };
        setFaceGuideColor(centered ? "green" : "yellow");
        if (!verifyingRef.current) return;
        if (!centered) {
          setInstruction("Center your face inside the oval guide.");
          setProgress("Adjusting position...");
          return;
        }
        setInstruction("Perfect. Now blink once slowly.");
        setProgress(`Eye ratio: ${avgEAR.toFixed(3)}`);
        if (avgEAR < 0.18) {
          eyesClosedFramesRef.current += 1;
        } else {
          if (eyesClosedFramesRef.current >= 2) blinkDetectedRef.current = true;
          eyesClosedFramesRef.current = 0;
        }
      });
      faceMeshRef.current = mesh;
    };
    document.body.appendChild(script);
    return () => {
      if (streamRef.current) streamRef.current.getTracks().forEach((t) => t.stop());
    };
  }, []);

  const runDetectionLoop = async () => {
    detectionLoopRef.current = true;
    while (videoRef.current && videoRef.current.srcObject && faceMeshRef.current) {
      try {
        await faceMeshRef.current.send({ image: videoRef.current });
      } catch (e) {}
      await sleep(120);
    }
    detectionLoopRef.current = false;
  };

  const startCamera = async () => {
    try {
      if (streamRef.current) streamRef.current.getTracks().forEach((t) => t.stop());
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480 },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
      setCameraStarted(true);
      setAuthStatus(null);
      setResult(null);
      setInstruction("Camera active. Align your face in the oval.");
      setProgress("Waiting for face detection...");
      if (!detectionLoopRef.current) runDetectionLoop();
    } catch (error) {
      setInstruction(`Camera error: ${error.message}`);
    }
  };

  const resetAttempt = () => {
    verifyingRef.current = false;
    blinkDetectedRef.current = false;
    eyesClosedFramesRef.current = 0;
    setAuthStatus(null);
    setResult(null);
    setInstruction("Attempt reset. Align your face and try again.");
    setProgress("");
  };

  const verifyIdentity = async () => {
    if (!username.trim()) {
      setInstruction("Please enter your username to continue.");
      return;
    }
    if (!cameraStarted || !videoRef.current?.srcObject) {
      setInstruction("Please start the camera first.");
      return;
    }
    resetAttempt();
    verifyingRef.current = true;
    setInstruction("Align your face and blink once.");
    setProgress("Initialising verification...");

    let waitTime = 0;
    while (waitTime < 10000) {
      if (!latestFaceDataRef.current.faceDetected) {
        setInstruction("No face detected. Move closer to the camera.");
      } else if (!latestFaceDataRef.current.centered) {
        setInstruction("Face detected. Centre yourself in the oval.");
      } else if (blinkDetectedRef.current) {
        break;
      }
      await sleep(150);
      waitTime += 150;
    }

    if (!blinkDetectedRef.current) {
      verifyingRef.current = false;
      setInstruction("Blink not detected. Please try again.");
      setProgress("Verification timed out.");
      return;
    }

    setInstruction("Blink confirmed. Hold still — capturing frames.");
    setProgress("Preparing capture...");
    await sleep(500);

  const canvas = canvasRef.current;
const video = videoRef.current;
const context = canvas.getContext("2d");

// Use actual video dimensions instead of hardcoded values
canvas.width = video.videoWidth || 640;
canvas.height = video.videoHeight || 480;

const formData = new FormData();
formData.append("username", username.trim());
formData.append("liveness_passed", "true");

setLoading(true);
for (let i = 0; i < 3; i++) {
  // Wait for video to be ready
  await sleep(200);
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  
  const blob = await new Promise((resolve) =>
    canvas.toBlob((b) => resolve(b), "image/jpeg", 0.95)
  );

  // Check blob is not empty
  if (!blob || blob.size < 1000) {
    setInstruction("Frame capture failed. Ensure camera is active.");
    setLoading(false);
    return;
  }

  formData.append("images", blob, `frame_${i + 1}.jpg`);
  setProgress(`Captured frame ${i + 1} of 3...`);
  await sleep(400);
}

    setProgress("Sending to server for verification...");
    verifyingRef.current = false;

    try {
      const response = await fetch("http://127.0.0.1:8000/api/login-multiframe/", {
        method: "POST",
        body: formData,
      });

      const contentType = response.headers.get("content-type") || "";
      if (!contentType.includes("application/json")) {
        const text = await response.text();
        setInstruction("Unexpected server response. Check console.");
        setProgress(text.slice(0, 200));
        return;
      }

      const data = await response.json();
      setAuthStatus(data.status === "Access Granted" ? "granted" : "denied");
      setResult(data);

      if (data.status === "Access Granted") {
        setInstruction("Identity verified. Redirecting to dashboard...");
        setProgress("");
        sessionStorage.setItem("username", username.trim());
        setTimeout(() => {
          window.location.href = "http://127.0.0.1:8000/dashboard/";
        }, 2000);
      } else {
        setInstruction("Authentication failed. Please reset and try again.");
        setProgress("");
      }
    } catch (error) {
      setInstruction(`Request failed: ${error.message}`);
      setProgress("");
    } finally {
      setLoading(false);
    }
  };

  const guideStyle = {
    red: { border: "3px dashed #ef4444", boxShadow: "0 0 20px rgba(239,68,68,0.6)" },
    yellow: { border: "3px dashed #f59e0b", boxShadow: "0 0 20px rgba(245,158,11,0.6)" },
    green: { border: "3px dashed #22c55e", boxShadow: "0 0 20px rgba(34,197,94,0.7)" },
  };

  const statusColor = {
    granted: "#22c55e",
    denied: "#ef4444",
    null: "transparent",
  };

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontFamily: "'Segoe UI', Arial, sans-serif",
      padding: 20,
    }}>
      <div style={{ width: "100%", maxWidth: 900 }}>

        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 10,
            background: "rgba(59,130,246,0.1)",
            border: "1px solid rgba(59,130,246,0.3)",
            borderRadius: 50, padding: "6px 18px", marginBottom: 16,
          }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: cameraStarted ? "#22c55e" : "#94a3b8", boxShadow: cameraStarted ? "0 0 8px #22c55e" : "none" }} />
            <span style={{ color: "#94a3b8", fontSize: 13, letterSpacing: 2, textTransform: "uppercase" }}>
              {cameraStarted ? "System Active" : "System Standby"}
            </span>
          </div>
          <h1 style={{ color: "#f1f5f9", fontSize: 28, fontWeight: 700, margin: 0, letterSpacing: 1 }}>
            Biometric Identity Verification
          </h1>
          <p style={{ color: "#64748b", fontSize: 14, marginTop: 8 }}>
            University Voting Authentication System — Pattern-Based Facial Recognition
          </p>
        </div>

        {/* Main Card */}
        <div style={{
          background: "rgba(15,23,42,0.8)",
          border: "1px solid rgba(59,130,246,0.2)",
          borderRadius: 20,
          padding: 32,
          backdropFilter: "blur(10px)",
        }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32 }}>

            {/* Left — Controls */}
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

              <div>
                <label style={{ color: "#94a3b8", fontSize: 12, letterSpacing: 1, textTransform: "uppercase", display: "block", marginBottom: 8 }}>
                  Voter ID / Username
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter your username"
                  style={{
                    width: "100%", padding: "12px 16px", fontSize: 15,
                    background: "rgba(30,41,59,0.8)",
                    border: "1px solid rgba(59,130,246,0.3)",
                    borderRadius: 10, color: "#f1f5f9",
                    outline: "none", boxSizing: "border-box",
                  }}
                />
              </div>

              {/* Buttons */}
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <button onClick={startCamera} style={{
                  padding: "12px 20px", fontSize: 14, fontWeight: 600,
                  background: cameraStarted ? "rgba(30,41,59,0.6)" : "rgba(59,130,246,0.8)",
                  color: "#f1f5f9", border: "1px solid rgba(59,130,246,0.4)",
                  borderRadius: 10, cursor: "pointer", transition: "all 0.2s",
                  letterSpacing: 0.5,
                }}>
                  {cameraStarted ? "🟢 Camera Running" : "📷 Start Camera"}
                </button>

                <button onClick={verifyIdentity} disabled={loading} style={{
                  padding: "12px 20px", fontSize: 14, fontWeight: 600,
                  background: loading ? "rgba(30,41,59,0.4)" : "rgba(34,197,94,0.15)",
                  color: loading ? "#64748b" : "#22c55e",
                  border: `1px solid ${loading ? "rgba(100,116,139,0.3)" : "rgba(34,197,94,0.4)"}`,
                  borderRadius: 10, cursor: loading ? "not-allowed" : "pointer",
                  transition: "all 0.2s", letterSpacing: 0.5,
                }}>
                  {loading ? "⏳ Verifying Identity..." : "🔐 Verify Identity"}
                </button>

                <button onClick={resetAttempt} style={{
                  padding: "12px 20px", fontSize: 14, fontWeight: 600,
                  background: "rgba(30,41,59,0.4)",
                  color: "#94a3b8", border: "1px solid rgba(100,116,139,0.3)",
                  borderRadius: 10, cursor: "pointer", letterSpacing: 0.5,
                }}>
                  🔄 Reset Attempt
                </button>
              </div>

              {/* Status panels */}
              <div style={{
                background: "rgba(30,41,59,0.6)",
                border: "1px solid rgba(59,130,246,0.15)",
                borderRadius: 10, padding: 14,
              }}>
                <p style={{ color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: 1, margin: "0 0 6px" }}>Instruction</p>
                <p style={{ color: "#cbd5e1", fontSize: 14, margin: 0, lineHeight: 1.5 }}>{instruction}</p>
              </div>

              {progress && (
                <div style={{
                  background: "rgba(30,41,59,0.6)",
                  border: "1px solid rgba(59,130,246,0.15)",
                  borderRadius: 10, padding: 14,
                }}>
                  <p style={{ color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: 1, margin: "0 0 6px" }}>Progress</p>
                  <p style={{ color: "#94a3b8", fontSize: 13, margin: 0 }}>{progress}</p>
                </div>
              )}

              {/* Result card */}
              {result && (
                <div style={{
                  background: authStatus === "granted" ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)",
                  border: `1px solid ${authStatus === "granted" ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`,
                  borderRadius: 10, padding: 14,
                }}>
                  <p style={{ color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: 1, margin: "0 0 10px" }}>Result</p>
                  <p style={{ color: statusColor[authStatus], fontSize: 16, fontWeight: 700, margin: "0 0 8px" }}>
                    {authStatus === "granted" ? "✅ Access Granted" : "❌ Access Denied"}
                  </p>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                    {[
                      ["Avg Distance", result.average_distance?.toFixed(4) ?? "N/A"],
                      ["Valid Frames", result.valid_frames ?? "N/A"],
                      ["Threshold", result.threshold ?? "N/A"],
                      ["Suspicious", result.suspicious ? "Yes" : "No"],
                    ].map(([label, value]) => (
                      <div key={label} style={{
                        background: "rgba(15,23,42,0.5)", borderRadius: 8, padding: "8px 10px",
                      }}>
                        <p style={{ color: "#64748b", fontSize: 10, textTransform: "uppercase", margin: "0 0 2px" }}>{label}</p>
                        <p style={{ color: "#cbd5e1", fontSize: 14, fontWeight: 600, margin: 0 }}>{value}</p>
                      </div>
                    ))}
                  </div>
                  {result.all_distances && (
                    <p style={{ color: "#64748b", fontSize: 12, margin: "10px 0 0" }}>
                      Frame distances: {result.all_distances.map(d => d.toFixed(4)).join(", ")}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Right — Camera */}
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{
                position: "relative", borderRadius: 16, overflow: "hidden",
                border: `2px solid ${faceGuideColor === "green" ? "rgba(34,197,94,0.5)" : faceGuideColor === "yellow" ? "rgba(245,158,11,0.5)" : "rgba(239,68,68,0.3)"}`,
                background: "#000", transition: "border-color 0.3s",
              }}>
                <video ref={videoRef} autoPlay playsInline style={{ width: "100%", display: "block" }} />
                {cameraStarted && (
                  <div style={{
                    position: "absolute", top: "50%", left: "50%",
                    width: "42%", height: "72%",
                    transform: "translate(-50%, -50%)",
                    borderRadius: "50% / 45%",
                    pointerEvents: "none",
                    boxSizing: "border-box",
                    transition: "all 0.3s ease",
                    ...guideStyle[faceGuideColor],
                  }} />
                )}
                {/* Corner decorations */}
                {["top:8px;left:8px", "top:8px;right:8px", "bottom:8px;left:8px", "bottom:8px;right:8px"].map((pos, i) => (
                  <div key={i} style={{
                    position: "absolute",
                    ...Object.fromEntries(pos.split(";").map(p => p.split(":"))),
                    width: 16, height: 16,
                    borderTop: i < 2 ? "2px solid rgba(59,130,246,0.5)" : "none",
                    borderBottom: i >= 2 ? "2px solid rgba(59,130,246,0.5)" : "none",
                    borderLeft: i % 2 === 0 ? "2px solid rgba(59,130,246,0.5)" : "none",
                    borderRight: i % 2 === 1 ? "2px solid rgba(59,130,246,0.5)" : "none",
                  }} />
                ))}
                {!cameraStarted && (
                  <div style={{
                    position: "absolute", inset: 0, display: "flex",
                    flexDirection: "column", alignItems: "center", justifyContent: "center",
                    background: "rgba(0,0,0,0.7)",
                  }}>
                    <div style={{ fontSize: 40, marginBottom: 10 }}>📷</div>
                    <p style={{ color: "#64748b", fontSize: 14 }}>Camera not started</p>
                  </div>
                )}
              </div>

              {/* Face status indicator */}
              <div style={{
                background: "rgba(30,41,59,0.6)",
                border: "1px solid rgba(59,130,246,0.15)",
                borderRadius: 10, padding: "10px 14px",
                display: "flex", alignItems: "center", gap: 10,
              }}>
                <div style={{
                  width: 10, height: 10, borderRadius: "50%",
                  background: faceGuideColor === "green" ? "#22c55e" : faceGuideColor === "yellow" ? "#f59e0b" : "#ef4444",
                  boxShadow: `0 0 8px ${faceGuideColor === "green" ? "#22c55e" : faceGuideColor === "yellow" ? "#f59e0b" : "#ef4444"}`,
                  flexShrink: 0,
                }} />
                <span style={{ color: "#94a3b8", fontSize: 13 }}>
                  {faceGuideColor === "green" ? "Face centred and ready" : faceGuideColor === "yellow" ? "Face detected — adjust position" : "No face detected"}
                </span>
              </div>

              {/* Security info */}
              <div style={{
                background: "rgba(30,41,59,0.4)",
                border: "1px solid rgba(59,130,246,0.1)",
                borderRadius: 10, padding: 14,
              }}>
                <p style={{ color: "#475569", fontSize: 11, textTransform: "uppercase", letterSpacing: 1, margin: "0 0 8px" }}>Security Features</p>
                {[
                  ["🔵", "Multi-frame facial recognition"],
                  ["🟢", "Liveness detection via blink"],
                  ["🟡", "Behavioural pattern analysis"],
                  ["🔴", "Isolation Forest anomaly detection"],
                ].map(([dot, text]) => (
                  <div key={text} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                    <span style={{ fontSize: 8 }}>{dot}</span>
                    <span style={{ color: "#64748b", fontSize: 12 }}>{text}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <p style={{ textAlign: "center", color: "#334155", fontSize: 12, marginTop: 20 }}>
          Pattern-Based Authentication System — University Voting Security
        </p>
      </div>

      <canvas ref={canvasRef} style={{ display: "none" }} />
    </div>
  );
}
import React, { useRef, useState, useEffect } from "react";

export default function ReactFaceAuthFrontend() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);

  const [username, setUsername] = useState("");
  const [cameraStarted, setCameraStarted] = useState(false);
  const [livenessPassed, setLivenessPassed] = useState(false);
  const [instruction, setInstruction] = useState("Instruction will appear here.");
  const [progress, setProgress] = useState("Progress will appear here.");
  const [result, setResult] = useState("Result will appear here.");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  const startCamera = async () => {
    try {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480 },
        audio: false,
      });

      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }

      setCameraStarted(true);
      setResult("Camera started successfully.");
    } catch (error) {
      setResult(`Camera error: ${error.message}`);
    }
  };

  const startLiveness = async () => {
    if (!cameraStarted) {
      setResult("Please start camera first.");
      return;
    }

    setInstruction("Please blink once to prove liveness.");
    setProgress("For now, click 'I Blinked' after blinking. We can replace this with automatic detection next.");
    setLivenessPassed(false);
  };

  const confirmBlink = () => {
    setLivenessPassed(true);
    setInstruction("Liveness passed. You may now login.");
    setProgress("Ready for multi-frame authentication.");
  };

  const captureLogin = async () => {
    if (!username.trim()) {
      setResult("Please enter username.");
      return;
    }

    if (!cameraStarted || !videoRef.current || !videoRef.current.srcObject) {
      setResult("Please start camera first.");
      return;
    }

    if (!livenessPassed) {
      setResult("Please complete liveness check first.");
      return;
    }

    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) {
      setResult("Camera elements are not ready.");
      return;
    }

    const context = canvas.getContext("2d");
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;

    const formData = new FormData();
    formData.append("username", username.trim());

    setLoading(true);
    setProgress("Capturing 3 frames... Please keep your face steady.");

    try {
      for (let i = 0; i < 3; i++) {
        context.drawImage(video, 0, 0, canvas.width, canvas.height);

        const blob = await new Promise((resolve) => {
          canvas.toBlob(resolve, "image/jpeg", 0.9);
        });

        if (!blob) {
          throw new Error("Failed to capture image frame.");
        }

        formData.append("images", blob, `frame_${i + 1}.jpg`);
        setProgress(`Captured frame ${i + 1} of 3`);
        await sleep(500);
      }

      setProgress("Sending frames for verification...");

      const response = await fetch("http://127.0.0.1:8000/api/login-multiframe/", {
        method: "POST",
        body: formData,
      });

      const contentType = response.headers.get("content-type") || "";
      if (!contentType.includes("application/json")) {
        const text = await response.text();
        setResult(`Server returned non-JSON response: ${text.slice(0, 300)}`);
        setProgress("");
        return;
      }

      const data = await response.json();

      setResult(
        `Status: ${data.status || data.error} | Average Distance: ${
          data.average_distance ?? "N/A"
        } | Valid Frames: ${data.valid_frames ?? "N/A"} | Threshold: ${
          data.threshold ?? "N/A"
        }`
      );
      setProgress(data.all_distances ? `Distances: ${data.all_distances.join(", ")}` : "");

      if (data.status === "Access Granted") {
        setTimeout(() => {
          window.location.href = "/dashboard/";
        }, 1200);
      }
    } catch (error) {
      setProgress("");
      setResult(`Request failed: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 p-6">
      <div className="mx-auto max-w-4xl rounded-3xl bg-white p-8 shadow-xl">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            University Voting Face Authentication
          </h1>
          <p className="mt-2 text-slate-600">
            React frontend for biometric login, liveness confirmation, and multi-frame verification.
          </p>
        </div>

        <div className="grid gap-8 md:grid-cols-2">
          <div className="space-y-4">
            <label className="block text-left text-sm font-medium text-slate-700">
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter username"
              className="w-full rounded-2xl border border-slate-300 px-4 py-3 outline-none focus:ring-2 focus:ring-slate-400"
            />

            <div className="flex flex-wrap gap-3">
              <button
                onClick={startCamera}
                className="rounded-2xl bg-slate-900 px-4 py-3 text-white shadow hover:bg-slate-800"
              >
                Start Camera
              </button>
              <button
                onClick={startLiveness}
                className="rounded-2xl bg-blue-600 px-4 py-3 text-white shadow hover:bg-blue-500"
              >
                Start Liveness Check
              </button>
              <button
                onClick={confirmBlink}
                className="rounded-2xl bg-amber-500 px-4 py-3 text-white shadow hover:bg-amber-400"
              >
                I Blinked
              </button>
              <button
                onClick={captureLogin}
                disabled={loading || !livenessPassed}
                className="rounded-2xl bg-emerald-600 px-4 py-3 text-white shadow hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "Authenticating..." : "Login with 3 Frames"}
              </button>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
              <p><span className="font-semibold">Instruction:</span> {instruction}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
              <p><span className="font-semibold">Progress:</span> {progress}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
              <p><span className="font-semibold">Result:</span> {result}</p>
            </div>
          </div>

          <div className="space-y-4">
            <div className="overflow-hidden rounded-3xl border-2 border-slate-300 bg-black shadow-inner">
              <video ref={videoRef} autoPlay playsInline className="h-auto w-full" />
            </div>
            <canvas ref={canvasRef} className="hidden" />
            <div className="rounded-2xl bg-slate-50 p-4 text-left text-sm text-slate-600">
              <p className="font-semibold text-slate-800">Current React scope</p>
              <p className="mt-2">
                This page replaces the plain HTML frontend while keeping your Django REST backend unchanged.
                It is safe to continue Objective 2 and Objective 3 after this because React only affects the interface layer.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

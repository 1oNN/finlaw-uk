import { useEffect, useRef, useState } from "react";
import { FiMic } from "react-icons/fi";

// Voice input via the browser Web Speech API. Chrome / Edge on Windows
// support `webkitSpeechRecognition`; Firefox and Safari iOS don't —
// MicButton renders `null` in that case so the composer simply omits
// it instead of breaking.
//
// `continuous=false` means the recognizer stops on its own after a
// short silence, which suits a chat-input use case. `interimResults`
// is on so the final-transcript event fires reasonably fast on partial
// utterances; only the final transcript is forwarded to the parent.
export default function MicButton({ onTranscript }) {
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const recRef = useRef(null);

  useEffect(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    setSupported(Boolean(SR));
  }, []);

  useEffect(() => {
    return () => {
      try {
        recRef.current?.stop();
      } catch {}
    };
  }, []);

  if (!supported) return null;

  const start = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new SR();
    rec.lang = "en-GB";
    rec.continuous = false;
    rec.interimResults = true;
    rec.onresult = (e) => {
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) {
          const text = e.results[i][0].transcript.trim();
          if (text) onTranscript?.(text);
        }
      }
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recRef.current = rec;
    setListening(true);
    try {
      rec.start();
    } catch {
      setListening(false);
    }
  };

  const stop = () => {
    try {
      recRef.current?.stop();
    } catch {}
    setListening(false);
  };

  return (
    <button
      type="button"
      onClick={listening ? stop : start}
      className={[
        "grid h-10 w-9 flex-none place-items-center transition-colors",
        listening ? "animate-pulse text-danger" : "text-ink-mute hover:text-accent",
      ].join(" ")}
      title={listening ? "Stop listening" : "Voice input"}
      aria-label={listening ? "Stop listening" : "Voice input"}
      aria-pressed={listening}
    >
      <FiMic size={15} />
    </button>
  );
}

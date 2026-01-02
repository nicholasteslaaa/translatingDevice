import { useState, useRef } from 'react';
import './App.css';

interface TranslationResponse {
  original_text: string;
  translated_text: string;
  status?: string;
  error?: string;
}

function App() {
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [result, setResult] = useState<TranslationResponse | null>(null);
  
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Determine supported mime type
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') 
                       ? 'audio/webm;codecs=opus' 
                       : 'audio/webm';

      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        // Create the blob immediately upon stopping
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        
        console.log(`Final Blob size: ${audioBlob.size} bytes`);

        if (audioBlob.size < 2000) {
          alert("Recording too short. Please speak for at least 1-2 seconds.");
        } else {
          await sendToApi(audioBlob);
        }

        // Clean up tracks
        stream.getTracks().forEach(track => track.stop());
      };

      // CRITICAL FIX: The '200' tells the recorder to provide data every 200ms
      // This prevents empty/corrupted headers on stop.
      recorder.start(200); 
      setIsRecording(true);
      setResult(null); 
    } catch (err) {
      console.error("Mic access denied", err);
      alert("Could not access microphone. Please check permissions.");
    }
  };

  const sendToApi = async (blob: Blob) => {
    setIsProcessing(true);
    const formData = new FormData();
    // We name it 'file' to match FastAPI's (file: UploadFile = File(...))
    formData.append('file', blob, 'recording.webm');

    try {
      const response = await fetch("https://api.rosblok.shop/translatingVoice", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error(`Server returned ${response.status}`);

      const data = await response.json();
      setResult(data);
    } catch (error) {
      console.error("API Error:", error);
      alert("Failed to connect to the translation server.");
    } finally {
      setIsProcessing(false);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  return (
    <div className="App" style={{ textAlign: 'center', padding: '50px', fontFamily: 'sans-serif' }}>
      <h1>Voice Translator</h1>
      
      <div style={{ margin: '20px 0' }}>
        <button 
          onClick={isRecording ? stopRecording : startRecording}
          disabled={isProcessing}
          style={{ 
            padding: '20px 40px', 
            fontSize: '18px', 
            cursor: 'pointer',
            backgroundColor: isRecording ? '#ff4d4d' : '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '10px'
          }}
        >
          {isProcessing ? '⏳ Processing...' : isRecording ? '⏹️ Stop & Translate' : '🎙️ Start Recording'}
        </button>
      </div>

      {isRecording && <p style={{ color: 'red', fontWeight: 'bold' }}>● Recording...</p>}

      {result && (
        <div style={{ marginTop: '30px', border: '1px solid #ccc', padding: '20px', borderRadius: '15px', backgroundColor: '#f9f9f9' }}>
          {result.error ? (
            <p style={{ color: 'red' }}>Error: {result.error}</p>
          ) : (
            <>
              <div style={{ marginBottom: '15px' }}>
                <small style={{ color: '#666' }}>You said (English):</small>
                <p style={{ fontSize: '18px', margin: '5px 0' }}>{result.original_text}</p>
              </div>
              <hr style={{ border: '0', borderTop: '1px solid #eee' }} />
              <div style={{ marginTop: '15px' }}>
                <small style={{ color: '#666' }}>Japanese Translation:</small>
                <p style={{ fontSize: '26px', color: '#007bff', margin: '5px 0', fontWeight: 'bold' }}>
                  {result.translated_text}
                </p>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
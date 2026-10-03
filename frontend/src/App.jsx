import { useEffect, useRef, useState } from "react";

const WS_URL = "ws://localhost:8000/ws";

const LANGUAGES = [
  { code: "en", speech: "en-IN", label: "English" },
  { code: "hi", speech: "hi-IN", label: "Hindi" },
  { code: "mr", speech: "mr-IN", label: "Marathi" },
  { code: "bn", speech: "bn-IN", label: "Bengali" },
  { code: "gu", speech: "gu-IN", label: "Gujarati" },
  { code: "ta", speech: "ta-IN", label: "Tamil" },
  { code: "te", speech: "te-IN", label: "Telugu" },
  { code: "kn", speech: "kn-IN", label: "Kannada" },
];

const QUICK_REACTIONS = ["👍", "❤️", "😂", "👏", "🎉", "🔥", "😊", "🤔"];

function getLanguage(code) {
  return (
    LANGUAGES.find((language) => language.code === code) ||
    LANGUAGES[0]
  );
}

function getSpeechRecognition() {
  return (
    window.SpeechRecognition ||
    window.webkitSpeechRecognition ||
    null
  );
}

function App() {
  const [page, setPage] = useState("home");
  const [name, setName] = useState("");
  const [roomCode, setRoomCode] = useState("");
  const [speakLanguage, setSpeakLanguage] = useState("en");
  const [preferredLanguage, setPreferredLanguage] = useState("hi");

  const [joined, setJoined] = useState(false);
  const [participants, setParticipants] = useState([]);
  const [captions, setCaptions] = useState([]);
  const [reactions, setReactions] = useState([]);
  const [connection, setConnection] = useState("Disconnected");
  const [micOn, setMicOn] = useState(false);
  const [error, setError] = useState("");
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [translationStatus, setTranslationStatus] =
    useState("Original");

  const socketRef = useRef(null);
  const streamRef = useRef(null);
  const recognitionRef = useRef(null);
  const recognitionActiveRef = useRef(false);
  const restartTimerRef = useRef(null);
  const joinedRef = useRef(false);
  const clientIdRef = useRef(crypto.randomUUID());

  function openJoin() {
    setError("");
    setPage("join");
  }

  function leaveRoom() {
    stopSpeechRecognition();

    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    setMicOn(false);
    setJoined(false);
    joinedRef.current = false;
    setParticipants([]);
    setCaptions([]);
    setReactions([]);
    setConnection("Disconnected");
    setPage("home");
  }

  function stopSpeechRecognition() {
    recognitionActiveRef.current = false;

    if (restartTimerRef.current) {
      clearTimeout(restartTimerRef.current);
      restartTimerRef.current = null;
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // Already stopped.
      }

      recognitionRef.current = null;
    }
  }

  function sendMessage(message) {
    const socket = socketRef.current;

    if (
      socket &&
      socket.readyState === WebSocket.OPEN
    ) {
      socket.send(JSON.stringify(message));
      return true;
    }

    return false;
  }

  function handleIncomingCaption(message) {
    const captionText = String(
      message.text || ""
    ).trim();

    if (!captionText) {
      return;
    }

    const originalText = String(
      message.original_text ||
        message.originalText ||
        captionText
    ).trim();

    const translated =
      message.target_language &&
      message.source_language &&
      message.target_language !==
        message.source_language;

    const targetLanguage =
      message.target_language ||
      preferredLanguage;

    setTranslationStatus(
      translated
        ? `Translated to ${
            getLanguage(targetLanguage).label
          }`
        : "Original"
    );

    setCaptions((current) => [
      ...current.slice(-49),
      {
        ...message,
        originalText,
        text: captionText,
        translated,
        targetLanguage,
      },
    ]);
  }

  function startSpeechRecognition() {
    const SpeechRecognitionAPI =
      getSpeechRecognition();

    if (!SpeechRecognitionAPI) {
      setError(
        "Live speech recognition is not supported in this browser. Try Chrome."
      );
      return;
    }

    stopSpeechRecognition();

    const recognition =
      new SpeechRecognitionAPI();

    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang =
      getLanguage(speakLanguage).speech;

    if ("maxAlternatives" in recognition) {
      recognition.maxAlternatives = 1;
    }

    recognition.onstart = () => {
      setConnection("Listening");
    };

    recognition.onresult = (event) => {
      let interimText = "";

      for (
        let index = event.resultIndex;
        index < event.results.length;
        index += 1
      ) {
        const result = event.results[index];

        if (result.isFinal) {
          const finalText =
            result[0]?.transcript?.trim();

          if (finalText) {
            const sent = sendMessage({
              type: "caption",
              text: finalText,
              source_language: speakLanguage,
              caption_id: crypto.randomUUID(),
              timestamp:
                new Date().toISOString(),
            });

            if (!sent) {
              setError(
                "Caption could not be sent. Check the room connection."
              );
            }
          }
        } else {
          interimText +=
            result[0]?.transcript || "";
        }
      }

      if (interimText.trim()) {
        setConnection("Listening");
      }
    };

    recognition.onerror = (event) => {
      if (
        event.error === "not-allowed" ||
        event.error === "service-not-allowed"
      ) {
        recognitionActiveRef.current = false;
        setError(
          "Speech recognition permission was denied."
        );
        setConnection("Connected");
        return;
      }

      if (event.error === "audio-capture") {
        setError(
          "The microphone could not be accessed."
        );
        setConnection("Connected");
        return;
      }

      if (
        event.error !== "no-speech" &&
        event.error !== "aborted" &&
        event.error !== "network"
      ) {
        console.warn(
          "Speech recognition error:",
          event.error
        );
      }
    };

    recognition.onend = () => {
      if (
        !recognitionActiveRef.current ||
        !joinedRef.current
      ) {
        return;
      }

      setConnection("Reconnecting speech...");

      restartTimerRef.current =
        setTimeout(() => {
          if (
            !recognitionActiveRef.current ||
            !joinedRef.current
          ) {
            return;
          }

          try {
            recognition.start();
          } catch {
            startSpeechRecognition();
          }
        }, 400);
    };

    recognitionRef.current = recognition;
    recognitionActiveRef.current = true;

    try {
      recognition.start();
    } catch (error) {
      console.warn(
        "Recognition start failed:",
        error
      );
    }
  }

  async function toggleMic() {
    if (micOn) {
      stopSpeechRecognition();

      if (streamRef.current) {
        streamRef.current
          .getTracks()
          .forEach((track) => track.stop());

        streamRef.current = null;
      }

      setMicOn(false);
      setConnection("Connected");
      return;
    }

    try {
      const stream =
        await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
          video: false,
        });

      streamRef.current = stream;

      setMicOn(true);
      setError("");

      startSpeechRecognition();
    } catch (err) {
      setError(
        err?.name === "NotAllowedError"
          ? "Microphone permission was denied."
          : "Microphone could not be opened."
      );
    }
  }

  function sendReaction(emoji) {
    sendMessage({
      type: "reaction",
      reaction: emoji,
    });

    setShowEmojiPicker(false);
  }

  function connectToRoom(
    displayName,
    code
  ) {
    setConnection("Connecting");

    const ws = new WebSocket(
      `${WS_URL}/${encodeURIComponent(
        code
      )}?name=${encodeURIComponent(
        displayName
      )}&client_id=${
        clientIdRef.current
      }&language=${encodeURIComponent(
        speakLanguage
      )}&caption_language=${encodeURIComponent(
        preferredLanguage
      )}`
    );

    socketRef.current = ws;

    ws.onopen = () => {
      setConnection("Connected");
      setJoined(true);
      joinedRef.current = true;
      setPage("room");

      sendMessage({
        type: "settings",
        name: displayName,
        language: speakLanguage,
        caption_language:
          preferredLanguage,
      });
    };

    ws.onmessage = async (event) => {
      try {
        const message =
          JSON.parse(event.data);

        if (message.type === "connected") {
          return;
        }

        if (message.type === "participants") {
          setParticipants(
            message.participants || []
          );
          return;
        }

        if (message.type === "caption") {
          handleIncomingCaption(message);
          return;
        }

        if (message.type === "reaction") {
          const reaction = {
            ...message,
            id: `${Date.now()}-${Math.random()}`,
          };

          setReactions((current) => [
            ...current.slice(-29),
            reaction,
          ]);

          setTimeout(() => {
            setReactions((current) =>
              current.filter(
                (item) =>
                  item.id !== reaction.id
              )
            );
          }, 3000);

          return;
        }
      } catch (messageError) {
        console.warn(
          "Invalid server message:",
          messageError
        );
      }
    };

    ws.onclose = () => {
      setConnection("Disconnected");

      if (joinedRef.current) {
        setError(
          "Connection closed. You can rejoin the room."
        );
      }
    };

    ws.onerror = () => {
      setConnection("Connection error");
      setError(
        "Could not connect to the Roundtable server."
      );
    };
  }

  function submitJoin(event) {
    event.preventDefault();

    const cleanName = name.trim();
    const cleanCode =
      roomCode.trim().toUpperCase();

    if (!cleanName || !cleanCode) {
      setError(
        "Enter both your name and room code."
      );
      return;
    }

    setError("");
    connectToRoom(
      cleanName,
      cleanCode
    );
  }

  function updatePreferredLanguage(event) {
    const language =
      event.target.value;

    setPreferredLanguage(language);

    sendMessage({
      type: "settings",
      caption_language: language,
    });
  }

  function updateSpeakLanguage(event) {
    const language =
      event.target.value;

    setSpeakLanguage(language);

    sendMessage({
      type: "settings",
      language,
    });

    if (micOn) {
      stopSpeechRecognition();

      setTimeout(() => {
        startSpeechRecognition();
      }, 300);
    }
  }

  useEffect(() => {
    return () => {
      stopSpeechRecognition();

      if (socketRef.current) {
        socketRef.current.close();
      }

      if (streamRef.current) {
        streamRef.current
          .getTracks()
          .forEach((track) =>
            track.stop()
          );
      }
    };
  }, []);

  if (page === "join") {
    return (
      <div className="app">
        <Header onJoin={openJoin} />

        <main className="join-page">
          <form
            className="join-card"
            onSubmit={submitJoin}
          >
            <div className="eyebrow">
              Shared multilingual captioning
            </div>

            <h1>Join a Roundtable</h1>

            <p>
              Choose the language you speak
              and the language you want to
              read.
            </p>

            <label>
              Display name
              <input
                value={name}
                onChange={(event) =>
                  setName(event.target.value)
                }
                placeholder="Your name"
                maxLength={40}
                autoFocus
              />
            </label>

            <label>
              Room code
              <input
                value={roomCode}
                onChange={(event) =>
                  setRoomCode(
                    event.target.value
                  )
                }
                placeholder="RT-4821"
                maxLength={12}
              />
            </label>

            <div className="language-grid">
              <label>
                I speak
                <select
                  value={speakLanguage}
                  onChange={(event) =>
                    setSpeakLanguage(
                      event.target.value
                    )
                  }
                >
                  {LANGUAGES.map(
                    (language) => (
                      <option
                        key={language.code}
                        value={language.code}
                      >
                        {language.label}
                      </option>
                    )
                  )}
                </select>
              </label>

              <label>
                Show captions in
                <select
                  value={
                    preferredLanguage
                  }
                  onChange={(event) =>
                    setPreferredLanguage(
                      event.target.value
                    )
                  }
                >
                  {LANGUAGES.map(
                    (language) => (
                      <option
                        key={language.code}
                        value={language.code}
                      >
                        {language.label}
                      </option>
                    )
                  )}
                </select>
              </label>
            </div>

            {error && (
              <div className="error">
                {error}
              </div>
            )}

            <div className="actions">
              <button
                type="button"
                className="btn"
                onClick={() =>
                  setPage("home")
                }
              >
                Cancel
              </button>

              <button
                className="btn primary"
                type="submit"
              >
                Enter room
              </button>
            </div>
          </form>
        </main>
      </div>
    );
  }

  if (page === "room") {
    return (
      <div className="app">
        <Header onJoin={openJoin} />

        <main className="room-page">
          <div className="room-header">
            <div>
              <div className="room-title">
                Roundtable ·{" "}
                {roomCode.toUpperCase()}
              </div>

              <div className="connection">
                <span className="dot" />
                {connection}
              </div>
            </div>

            <button
              className="btn"
              onClick={leaveRoom}
            >
              Leave room
            </button>
          </div>

          <div className="room-grid">
            <section className="panel captions">
              <div className="panel-head">
                <strong>
                  Live captions
                </strong>

                <span>
                  {translationStatus}
                </span>
              </div>

              <div className="caption-list">
                {captions.length === 0 ? (
                  <div className="empty">
                    <strong>
                      No live speech yet
                    </strong>

                    <span>
                      Turn on your microphone
                      and start speaking.
                    </span>
                  </div>
                ) : (
                  captions.map(
                    (caption, index) => (
                      <div
                        className="caption"
                        key={`${caption.timestamp}-${index}`}
                      >
                        <div>
                          <div className="speaker">
                            {
                              caption.speaker
                            }
                          </div>

                          <div className="caption-language">
                            {
                              getLanguage(
                                caption.source_language ||
                                  "en"
                              ).label
                            }
                          </div>
                        </div>

                        <div>
                          <div>
                            {caption.text}
                          </div>

                          {caption.translated &&
                            caption.originalText !==
                              caption.text && (
                              <details className="original-caption">
                                <summary>
                                  Show original
                                </summary>

                                <div>
                                  {
                                    caption.originalText
                                  }
                                </div>
                              </details>
                            )}
                        </div>
                      </div>
                    )
                  )
                )}
              </div>

              {reactions.length > 0 && (
                <div className="reaction-overlay">
                  {reactions.map(
                    (reaction) => (
                      <div
                        className="floating-reaction"
                        key={reaction.id}
                      >
                        <span>
                          {
                            reaction.reaction
                          }
                        </span>

                        <small>
                          {reaction.name}
                        </small>
                      </div>
                    )
                  )}
                </div>
              )}

              <div className="reaction-bar">
                <div className="reaction-picker-wrap">
                  <button
                    className="reaction-trigger"
                    onClick={() =>
                      setShowEmojiPicker(
                        (current) =>
                          !current
                      )
                    }
                  >
                    😊 React
                  </button>

                  {showEmojiPicker && (
                    <div className="emoji-picker">
                      {QUICK_REACTIONS.map(
                        (emoji) => (
                          <button
                            key={emoji}
                            className="emoji-button"
                            onClick={() =>
                              sendReaction(
                                emoji
                              )
                            }
                            aria-label={`Send ${emoji}`}
                          >
                            {emoji}
                          </button>
                        )
                      )}
                    </div>
                  )}
                </div>

                <span className="reaction-hint">
                  Send a quick reaction
                  to everyone
                </span>
              </div>
            </section>

            <aside className="panel sidebar">
              <div className="side-section">
                <div className="side-title">
                  Participants
                </div>

                {participants.map(
                  (person) => (
                    <div
                      className="participant"
                      key={person.client_id}
                    >
                      <span className="avatar">
                        {person.name
                          .slice(0, 2)
                          .toUpperCase()}
                      </span>

                      <span>
                        <strong>
                          {person.name}
                        </strong>

                        <small className="participant-language">
                          {getLanguage(
                            person.caption_language ||
                              "en"
                          ).label}
                        </small>
                      </span>

                      <span className="participant-dot" />
                    </div>
                  )
                )}
              </div>

              <div className="side-section">
                <div className="side-title">
                  Your languages
                </div>

                <label>
                  I speak
                  <select
                    value={speakLanguage}
                    onChange={
                      updateSpeakLanguage
                    }
                  >
                    {LANGUAGES.map(
                      (language) => (
                        <option
                          key={language.code}
                          value={
                            language.code
                          }
                        >
                          {language.label}
                        </option>
                      )
                    )}
                  </select>
                </label>

                <label>
                  Show captions in
                  <select
                    value={
                      preferredLanguage
                    }
                    onChange={
                      updatePreferredLanguage
                    }
                  >
                    {LANGUAGES.map(
                      (language) => (
                        <option
                          key={language.code}
                          value={
                            language.code
                          }
                        >
                          {language.label}
                        </option>
                      )
                    )}
                  </select>
                </label>
              </div>

              <div className="side-section">
                <div className="side-title">
                  Microphone
                </div>

                <div className="mic-row">
                  <span>
                    {micOn
                      ? "Microphone enabled"
                      : "Microphone off"}
                  </span>

                  <button
                    className={`mic-button ${
                      micOn
                        ? "active"
                        : ""
                    }`}
                    onClick={toggleMic}
                  >
                    {micOn ? "ON" : "OFF"}
                  </button>
                </div>
              </div>

              {error && (
                <div className="side-section">
                  <div className="error">
                    {error}
                  </div>
                </div>
              )}

              <div className="side-section">
                <div className="side-title">
                  Room reactions
                </div>

                <div className="reaction-mini-grid">
                  {QUICK_REACTIONS.map(
                    (emoji) => (
                      <button
                        key={emoji}
                        className="reaction-mini"
                        onClick={() =>
                          sendReaction(
                            emoji
                          )
                        }
                      >
                        {emoji}
                      </button>
                    )
                  )}
                </div>
              </div>
            </aside>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <Header onJoin={openJoin} />

      <main>
        <section className="hero container">
          <div>
            <div className="eyebrow">
              Shared multilingual live
              captioning
            </div>

            <div className="rule" />

            <h1>
              One conversation. Multiple
              languages. One shared room.
            </h1>

            <p className="hero-copy">
              Roundtable lets nearby devices
              contribute separate audio views
              while each participant reads the
              conversation in their preferred
              language.
            </p>

            <div className="actions">
              <button
                className="btn primary large"
                onClick={openJoin}
              >
                Join a session
              </button>

              <a
                className="btn large"
                href="#how"
              >
                See how it works
              </a>
            </div>

            <small>
              Browser-based prototype for
              multilingual group conversations.
            </small>
          </div>

          <div className="demo panel">
            <div className="panel-head">
              <span>Demo room</span>
              <span>Ready</span>
            </div>

            <div className="demo-body">
              <div className="caption">
                <div className="speaker">
                  Shitanshu
                </div>

                <div>
                  Good morning everyone,
                  welcome to the meeting.
                </div>
              </div>

              <div className="caption">
                <div className="speaker">
                  Hindi reader
                </div>

                <div>
                  सुप्रभात सभी को, बैठक में
                  आपका स्वागत है।
                </div>
              </div>

              <div className="caption">
                <div className="speaker">
                  Marathi reader
                </div>

                <div>
                  सर्वांना सुप्रभात, बैठकीत
                  तुमचे स्वागत आहे.
                </div>
              </div>

              <div className="caption">
                <div className="speaker">
                  Room
                </div>

                <div className="muted">
                  👍 👏 ❤️ 🎉
                </div>
              </div>
            </div>
          </div>
        </section>

        <section
          className="section"
          id="how"
        >
          <div className="container">
            <div className="section-heading">
              <h2>
                A shared conversation without
                a shared language barrier.
              </h2>

              <p>
                Each participant can choose
                what they speak and what
                language they want to read.
                Reactions stay universal across
                the room.
              </p>
            </div>

            <div className="cards">
              <Feature
                number="01"
                title="Multiple audio views"
              >
                Each participant contributes
                from their own device instead of
                relying on one microphone.
              </Feature>

              <Feature
                number="02"
                title="Personalized captions"
              >
                Participants can select a
                preferred caption language
                independently.
              </Feature>

              <Feature
                number="03"
                title="Shared reactions"
              >
                Quick emoji reactions let people
                respond without interrupting the
                conversation.
              </Feature>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

function Header({ onJoin }) {
  return (
    <header className="nav container">
      <div className="brand">
        <span className="brand-mark">
          R
        </span>

        <span>Roundtable</span>
      </div>

      <nav className="nav-links">
        <a href="#how">
          How it works
        </a>
      </nav>

      <button
        className="btn primary"
        onClick={onJoin}
      >
        Join a session
      </button>
    </header>
  );
}

function Feature({
  number,
  title,
  children,
}) {
  return (
    <article className="card">
      <div className="card-index">
        {number}
      </div>

      <h3>{title}</h3>

      <p>{children}</p>
    </article>
  );
}

export default App;
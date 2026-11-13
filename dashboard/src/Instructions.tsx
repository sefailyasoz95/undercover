import { useEffect, useState } from "react";
import { api } from "./api";

export function Instructions() {
  const [text, setText] = useState<string>();

  useEffect(() => {
    void api.instructions().then(({ text }) => {
      setText(text);
    });
  }, []);

  return (
    <section>
      <h1>The agent's instructions</h1>
      <p className="muted">
        Read only. The UnderCover Agent works from these on every claim.
      </p>
      <div className="panel">
        {text === undefined ? (
          <p>Loading...</p>
        ) : (
          <pre className="instructions">{text}</pre>
        )}
      </div>
    </section>
  );
}

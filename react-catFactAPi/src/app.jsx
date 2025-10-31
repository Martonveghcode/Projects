import React, { useState, useEffect } from "react";
import Body from "./Body";

export default function App() {
  const [fact, setFact] = useState(null);

  useEffect(() => {
    fetch("https://catfact.ninja/fact")
      .then((res) => res.json())
      .then((data) => setFact(data.fact))
      .catch((err) => console.error(err));
  }, []); // empty array = run once

  return (
    <div>
      {fact ? <Body fact={fact} /> : <p>Loading...</p>}
    </div>
  );
}

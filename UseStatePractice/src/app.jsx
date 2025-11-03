import { useState } from "react";

export default function App() {
  const [num, setNum] = useState(0); // ✅ useState must be called inside the component

  function handleClick() {
    setNum(num + 1); // ✅ correctly update state
  }

  return (
    <>
      <button className="click" onClick={handleClick}>Click</button>
      <p>{num}</p>
    </>
  );
}

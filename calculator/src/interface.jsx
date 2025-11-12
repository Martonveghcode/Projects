import { useState } from "react";

export default function Interface() {
  const [current, setCurrent] = useState("");   // digits you’re typing now
  const [previous, setPrevious] = useState(null); // stored first operand
  const [op, setOp] = useState(null);            // '+', '-', '*'

  function handleDigit(d) {
    setCurrent(prev => prev + String(d));
  }

  function compute(aStr, bStr, operation) {
    const a = Number(aStr ?? 0);
    const b = Number(bStr ?? 0);
    switch (operation) {
      case "+": return a + b;
      case "-": return a - b;
      case "*": return a * b;
      default: return b; // if no op, just show current
    }
  }

  function handleOperation(nextOp) {
    if (current === "" && previous !== null) {
      // user is switching operation without typing new digits
      setOp(nextOp);
      return;
    }

    if (previous === null) {
      // first time picking an operation
      setPrevious(current === "" ? "0" : current);
      setCurrent("");
      setOp(nextOp);
    } else {
      // chaining: compute previous op current, then set new op
      const result = compute(previous, current === "" ? "0" : current, op);
      setPrevious(String(result));
      setCurrent("");
      setOp(nextOp);
    }
  }

  function handleEquals() {
    if (op && previous !== null && current !== "") {
      const result = compute(previous, current, op);
      setCurrent(String(result));
      setPrevious(null);
      setOp(null);
    }
  }

  function handleClear() {
    setCurrent("");
    setPrevious(null);
    setOp(null);
  }

  const display =
    current !== ""
      ? current
      : previous !== null
      ? previous
      : "";

  return (
    <>
      <main>
        <header>
          <h2 className="output-el">{display}</h2>
        </header>

        <section className="keyboard">
          <section className="row1">
            <button onClick={() => handleDigit(1)} className="1">1</button>
            <button onClick={() => handleDigit(2)} className="2">2</button>
            <button onClick={() => handleDigit(3)} className="3">3</button>
            <button onClick={() => handleOperation("*")} className="X">X</button>
          </section>

          <section className="row2">
            <button onClick={() => handleDigit(4)} className="4">4</button>
            <button onClick={() => handleDigit(5)} className="5">5</button>
            <button onClick={() => handleDigit(6)} className="6">6</button>
            <button onClick={() => handleOperation("+")} className="+">+</button>
          </section>

          <section className="row3">
            <button onClick={() => handleDigit(7)} className="7">7</button>
            <button onClick={() => handleDigit(8)} className="8">8</button>
            <button onClick={() => handleDigit(9)} className="9">9</button>
            <button onClick={() => handleOperation("-")} className="-">-</button>
            <button onClick={handleEquals} className="=">=</button>
          </section>

          <section className="row4">
            <button onClick={() => handleDigit(0)} className="0">0</button>
            <button onClick={handleClear} className="clear">C</button>
          </section>
        </section>
      </main>
    </>
  );
}

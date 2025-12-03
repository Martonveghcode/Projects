import { useState } from "react";
import Chips from "./Chips";
import Header from "./Header";
import Keyboard from "./Keyboard";
import NewGame from "./Newgame-btn";
import Word from "./Word";

export default function App() {
    const [letters, setLetters] = useState([]);
    const [currentWord] = useState("default");
    const [colour, setColour] = useState(null);
    const [wrongGuessCount, setWrongGuessCount] = useState(0)

    function handleLetters(x) {
        setLetters(prev => (prev.includes(x) ? prev : [...prev, x]));
        const isCorrect = currentWord.includes(x);
        setColour(isCorrect ? "green" : "red");
        currentWord.includes(x) ? null : setWrongGuessCount(prev => prev + 1)
        console.log(wrongGuessCount)
    }

    return (
        <>
            <Header />
            <Chips />
            <Word word={currentWord} guessedLetters={letters} />
            <Keyboard letters={handleLetters} colour={colour} word={currentWord} letter={letters} />
            <NewGame />
        </>
    );
}

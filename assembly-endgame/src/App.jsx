import { useState } from "react"
import Chips from "./Chips"
import Header from "./Header"
import Keyboard from "./Keyboard"
import NewGame from "./Newgame-btn"
import Word from "./Word"
import { languages } from "./languages"
export default function App() {
    const [letters, setLetters] = useState([])
    const [currentWord] = useState("default")
    const [colour, setColour] = useState(null)
    const [wrongGuessCount, setWrongGuessCount] = useState(0)
    const chips = languages.map((language, index) => ({
        ...language,
        id: index,
        lost: index < wrongGuessCount,
    }))
    let isGameOver = false

    function handleLetters(x) {
        setLetters(prev => (prev.includes(x) ? prev : [...prev, x]))
        const isCorrect = currentWord.includes(x)
        setColour(isCorrect ? "green" : "red")
        if (!isCorrect) {
            setWrongGuessCount(prev => Math.min(prev + 1, languages.length))
        }
        console.log(wrongGuessCount)}

    function handleWrongGuess() {
        setWrongGuessCount(prev => Math.min(prev + 1, languages.length))
    }

    if (languages.length - wrongGuessCount === 1) {
        isGameOver = true
    }

    return (
        <>
            <Header gameOver={isGameOver} />
            <Chips handleWrong={handleWrongGuess} chips={chips}/>
            <Word word={currentWord} guessedLetters={letters} />
            <Keyboard letters={handleLetters} gameOver={isGameOver} colour={colour} word={currentWord} letter={letters} />
            <NewGame gameOver={isGameOver} />
        </>
    );
}

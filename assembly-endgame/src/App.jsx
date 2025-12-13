import { useMemo, useState } from "react"
import Chips from "./Chips"
import Header from "./Header"
import Keyboard from "./Keyboard"
import NewGame from "./Newgame-btn"
import Word from "./Word"
import { languages } from "./languages"
import { getFarewellText, setWord } from "./utils"
import Confetti from 'react-confetti'

export default function App() {
    const [letters, setLetters] = useState([])
    const [currentWord, setCurrentWord] = useState(() => setWord())
    const [colour, setColour] = useState(null)
    const [wrongGuessCount, setWrongGuessCount] = useState(0)
    const chips = languages.map((language, index) => ({
        ...language,
        id: index,
        lost: index < wrongGuessCount,
    }))
    let isGameOver = false
    let gameWon = false
    
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

   if (currentWord.split("").every(letter => letters.includes(letter))) {
        gameWon = true
        
    


   }

    

    function resetGame() {
        setLetters([])
        setWrongGuessCount(0)
        setColour(null)
        setCurrentWord(setWord())
    }

     const farewell = useMemo(() => {
        if (wrongGuessCount > 0 && wrongGuessCount <= languages.length) {
            const eliminatedLanguage = languages[wrongGuessCount - 1]
            const farewellMessage = getFarewellText(eliminatedLanguage.name)
            console.log(farewellMessage)
            return farewellMessage
        }
        return ""
    }, [wrongGuessCount])
    return (
        <>
            <Header farewell={farewell} gameWon={gameWon} gameOver={isGameOver} />
            <Chips handleWrong={handleWrongGuess} chips={chips}/>
            <Word won={gameWon} word={currentWord} guessedLetters={letters} />
            <Keyboard letters={handleLetters} gameOver={isGameOver} colour={colour} word={currentWord} letter={letters} />
            <NewGame onNewGame={resetGame} gameWon={gameWon} gameOver={isGameOver} />
            {gameWon ? <Confetti /> : null}
        </>
    );
}

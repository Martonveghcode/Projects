import { useEffect, useState } from "react"
import Die from "./Die"
import { nanoid } from "nanoid"
import Confetti from 'react-confetti'
export default function App() {
    
const [dice, setDice] = useState(() => generateAllNewDice())
    let btnText = "roll"
    let gameWon = false
    const allHeld = dice.every(die => die.isHeld)
const firstValue = dice[0].value
const allSameValue = dice.every(die => die.value === firstValue)

if (allHeld && allSameValue) {
    console.log("Game won!")
    gameWon = true
    btnText = "roll"
    
}
function newGame() {
    setDice(generateAllNewDice())
}

if (gameWon) {
    btnText = "new game"
    
  
}
useEffect(() => {
    document.getElementById("roll-dice-btn").focus({focusVisible : true})
},[gameWon])

    function generateAllNewDice() {
        
        console.log("was called")
        return new Array(10)
            .fill(0)
            .map(() => ({
                value: Math.ceil(Math.random() * 6),
                isHeld: false,
                id: nanoid()
        
            }))
    }

   

    function rollDice() {
        setDice(prevDice => prevDice.map( die => die.isHeld ? die : {
            ...die, value: Math.ceil(Math.random() * 6)
        }))
    }

    function hold(id) {
        setDice(oldDice => oldDice.map(die =>
            die.id === id ?
                { ...die, isHeld: !die.isHeld } :
                die
        ))
    }

    const diceElements = dice.map(dieObj => (
        <Die
            key={dieObj.id}
            value={dieObj.value}
            isHeld={dieObj.isHeld}
            hold={() => hold(dieObj.id)}
        />
    ))

    return (
        <main>
            {gameWon ? <Confetti/> : null}
            <h1>Tenzies-React</h1>
            <div className="dice-container">
                {diceElements}
            </div>
            <button id="roll-dice-btn" className="roll-dice" onClick={gameWon ? newGame : rollDice}>{btnText}</button>
        </main>
    )
}
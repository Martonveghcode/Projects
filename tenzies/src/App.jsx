import { useState } from "react"
import Die from "./Die"
import { nanoid } from "nanoid"

export default function App() {
    const [dice, setDice] = useState(generateAllNewDice())
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

if (gameWon) {
    btnText = "new game"
}

    function generateAllNewDice() {
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
            <h1>Tenzies-React</h1>
            <div className="dice-container">
                {diceElements}
            </div>
            <button className="roll-dice" onClick={gameWon ? generateAllNewDice : rollDice}>{btnText}</button>
        </main>
    )
}
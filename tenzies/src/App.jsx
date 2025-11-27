import { useState } from "react";
import Die from "./die";
import { nanoid } from "nanoid";


export default function App() {
    const [held, setheld] = useState(false)
    const [numbers, setNumbers] = useState(Array(10).fill(null))
    function generateAllNewDice() {
        
        setNumbers(numbers.map(() => <Die onBtn={hold} key={nanoid()}  isHeld={held} id={nanoid()} value={Math.floor(Math.random() * 6 + 1)}/> ))
        console.log(numbers)
    }
    function hold(key) {
        console.log(key)
        setheld( prevHeld => prevHeld.map(item => {
            return item.id === id ? {...item, isHeld : true } : item
        }))
        
    }

   

    return(<>
    <main>
        <div className="dieDiv">
            {numbers}
            
        </div>
        <button className="dice-btn" onClick={generateAllNewDice}>Role dice </button>
    </main>
    
    
    </>)
    
}
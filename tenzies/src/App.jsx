import { useState } from "react";
import Die from "./Die";

export default function App() {
    const [numbers, setNumbers] = useState(Array(10).fill(null))
    function generateAllNewDice() {
        
        setNumbers(numbers.map(() => <Die value={Math.floor(Math.random() * 6 + 1)}/> ))
        console.log(numbers)
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
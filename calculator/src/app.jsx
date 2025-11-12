import { useState } from "react"
// most likely wont use this one its deprecciated 
export default function App() {
    

        function handleNumbers(formData) {
            const numbers = Number(formData.get("numbers"))
            
           
            setNumbers((prevNumber) => prevNumber + numbers)
            console.log(number)
        }

        const [number, setNumbers] = useState(0)


        

    return(
    <>
        <form action={handleNumbers} >
            <label htmlFor="numbers">equation:</label>
            <input id="numbers"  name="numbers"  type="text" />
            <p className="output">{number}</p>

        </form>
    
    
    </>
    )
}

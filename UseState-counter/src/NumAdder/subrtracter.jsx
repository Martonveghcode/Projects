import { useState } from "react"

export default function Main() {
    
    const [num, setNum] = useState(0)

    function handleClick() {
        setNum(num + 1)
    }
    function handleClickNegative() {
        setNum(num - 1)
    }
    

    return(
        <>




        <h2>{num}</h2>
        <button className="input-btn" onClick={handleClick}>+1</button>
        <button className="input-btn" onClick={handleClickNegative}>-1</button>


        </>
    )
}
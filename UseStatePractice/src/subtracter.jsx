import { useState } from "react";

export default function Subtract() {
    const [num, setNum] = useState(0)

    function handleClick() {
        setNum(num - 1)
    }

    return(
        <>
            <p>this is a number:{num}</p>
            <button className="clickbtn" onClick={handleClick}>click for minus number</button>
        
        </>
    )


}
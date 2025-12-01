import { useState } from "react"
import { nanoid } from "nanoid"
export default function Word() {
    const [currentWord] = useState("Default")

    
   
    return (
        
        
        <section className="chips">{currentWord.split("").map((x) => <span key={nanoid()} className="word-p">{x}</span>)}</section>
        
        

    )
}
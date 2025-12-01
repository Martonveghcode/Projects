import { useState } from "react"
import { languages } from "./languages"

export default function Chips() {
    
    const [chips] = useState(Array.from({ length: 9 }, (_, i) => i))

    return(
        <>
            <section className="chips">
                {chips.map(x => (
                    <div className="languages-div" key={x} style={{background: languages[x].backgroundColor}}>
                        <p className="languages-p" style={{color: languages[x].color}}>{languages[x].name}</p>
                    </div>
                ))}
            </section>
        </>
    )
}
    
   


    

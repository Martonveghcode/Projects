import { useState } from "react"
import pads from "./pads"
import Pad from "./pad"

export default function App() {
    // eslint-disable-next-line no-unused-vars
    const [padsState, setPadsState] = useState(pads)
    

    function toggle() {
        console.log("clicked!")
    }
    return (
        <main>
            <div className="pad-container">
                {padsState.map(pad => (
                    <Pad key={pad.id} color={pad.color} func={toggle} 
                        
                    />))}
                
            </div>
        </main>
    )
}

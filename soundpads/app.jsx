import { useState } from "react"
import pads from "./pads"
import Pad from "./pad"

export default function App() {
    // eslint-disable-next-line no-unused-vars
    const [padsState, setPadsState] = useState(pads)
    

    function toggle(id) {
        console.log(id)
        setPadsState( prevPads => prevPads.map(pad => {if(pad.id === id) {
            return(pad = {...pad, on: !pad.on})
            
            
        }
    else {
        return pad
                
            }}) )
    }
    return (
        <main>
            <div className="pad-container">
                {padsState.map(pad => (
                    <Pad key={pad.id} id={pad.id} color={pad.color} on={pad.on} func={toggle} 
                        
                    />))}
                
            </div>
        </main>
    )
}

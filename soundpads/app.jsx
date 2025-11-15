import { useState } from "react"
import pads from "./pads"

export default function App() {
    const [padsState, setPadsState] = useState(pads)

    return (
        <main>
            <div className="pad-container">
                {padsState.map(pad => (
                    <button>
                        {pad}
                    </button>
                ))}
            </div>
        </main>
    )
}

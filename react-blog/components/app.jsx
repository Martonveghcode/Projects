import Entry from "./entry"
import Header from "./header"
import data from "../data.js"


export default function App() {

    const entryElements = data.map((entry) => {
        return <Entry
            {...entry}
            key={entry.id}
        
        />
    })


    return(
        <>
            <Header/>
            {entryElements}
            
            
            
        </>
    )
}
    

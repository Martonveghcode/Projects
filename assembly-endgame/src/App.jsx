import { useState } from "react";
import Chips from "./Chips";
import Header from "./Header";
import Keyboard from "./Keyboard";
import NewGame from "./Newgame-btn";
import Word from "./Word";
import { nanoid } from "nanoid";

export default function App() {
    const [letters, setLetters] = useState([])
    const [currentWord] = useState("default")
    const [colour, setColour] = useState(null)
    function handleLetters(x) {
        setLetters( prev => prev.includes(x) ? prev : [...letters, x])
        console.log(letters)
        currentWord.split("").includes(x) ? setColour("green" ) : setColour("red")
    }

    
    
    


    return(
        <>
            <Header/>
            <Chips/>
            <Word word={currentWord.split("").map((x) => <span key={nanoid()} className="word-p">{x}</span>)}/>
            <Keyboard letters={handleLetters} colour={colour} word={currentWord} letter={letters}/>
            <NewGame/>
        </>
    )


}
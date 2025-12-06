export default function Header(props) {
    return(
        <>
            <header>
            <h1>Assembly: Endgame</h1>
            <p>guess the word in under 8 attempts to keep
                 the programming world safe from Assembly!</p>
            
            {props.gameOver ? <div className="message-div" style={{backgroundColor: "red"}}>
                <p>You Lost!</p>
            </div> : props.gameWon ? <div className="message-div" style={{backgroundColor: "green"}}>
                <p>You Won!</p>
            </div> : null}
            </header>
        </>
    )
}
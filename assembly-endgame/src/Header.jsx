export default function Header(props) {
    const status = props.gameOver
        ? {
              text: "You Lost!",
              background: "red",
              className: "message-div",
              live: "assertive",
          }
        : props.gameWon
        ? {
              text: "You Won!",
              background: "green",
              className: "message-div",
              live: "assertive",
          }
        : {
              text: props.farewell || "",
              background: "purple",
              className: "wrong-answer-div",
              live: "polite",
          }

    return (
        <>
            <header aria-labelledby="game-title" aria-describedby="game-tagline">
                <h1 id="game-title">Assembly: Endgame</h1>
                <p id="game-tagline">
                    guess the word in under 8 attempts to keep the programming world safe from Assembly!
                </p>

                <div
                    className={status.className}
                    style={{ backgroundColor: status.background }}
                    role="status"
                    aria-live={status.live}
                    aria-atomic="true"
                >
                    <p className={props.gameOver || props.gameWon ? undefined : "wrong-p"}>{status.text}</p>
                </div>
            </header>
        </>
    )
}

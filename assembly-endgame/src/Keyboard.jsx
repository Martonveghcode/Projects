import clsx from "clsx"

export default function Keyboard(props) {
    const { letters: onLetterSelect, gameOver, word, letter } = props
    const alphabet = "abcdefghijklmnopqrstuvwxyz"
    const lettersInWord = word.split("")

    return (
        <>
            <section className="chips" role="group" aria-label="Letter keyboard">
                {alphabet.split("").map(character => {
                    const isGuessed = letter.includes(character)
                    const isCorrectGuess = isGuessed && lettersInWord.includes(character)
                    const isDisabled = gameOver || isGuessed
                    const labelParts = [`Letter ${character}`]
                    if (isGuessed) {
                        labelParts.push(isCorrectGuess ? "correct guess" : "incorrect guess")
                    }

                    return (
                        <button
                            type="button"
                            onClick={isDisabled ? undefined : () => onLetterSelect(character)}
                            key={character}
                            className={clsx("keyboard", isGuessed && (isCorrectGuess ? "green" : "red"))}
                            aria-label={labelParts.join(", ")}
                            aria-pressed={isGuessed}
                            disabled={isDisabled}
                        >
                            {character}
                        </button>
                    )
                })}
            </section>
        </>
    )
}

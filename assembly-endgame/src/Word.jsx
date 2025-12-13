import { nanoid } from "nanoid";

export default function Word({ word, guessedLetters, won }) {
    const accessibleWord = word
        .split("")
        .map(letter => (won || guessedLetters.includes(letter) ? letter : "blank"))
        .join(" ");

    const displayLetters = word.split("").map(letter => (won || guessedLetters.includes(letter) ? letter : ""))

    return (
        <section className="chips" aria-label="Word progress" aria-live="polite" aria-atomic="true">
            <span className="sr-only">{`Current progress: ${accessibleWord}`}</span>
            {displayLetters.map(letter => (
                <span key={nanoid()} className="word-p" aria-hidden="true">
                    {letter}
                </span>
            ))}
        </section>
    );
}

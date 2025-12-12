export default function Chips({ chips }) {
    return (
        <>
            <section className="chips" role="list" aria-label="Programming languages remaining">
                {chips.map(chip => {
                    const status = chip.lost ? "eliminated" : "still active"
                    return (
                        <div
                            className={`languages-div${chip.lost ? " lost" : ""}`}
                            key={chip.id}
                            style={{ background: chip.backgroundColor }}
                            role="listitem"
                            aria-label={`${chip.name} ${status}`}
                        >
                            <p className="languages-p" style={{ color: chip.color }}>
                                {chip.name}
                            </p>
                        </div>
                    )
                })}
            </section>
        </>
    )
}

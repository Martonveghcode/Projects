export default function App(props) {
  return (
    <div>
      {props.num.map((n) => (
        <p>{n}</p>
      ))}
    </div>
  );
}

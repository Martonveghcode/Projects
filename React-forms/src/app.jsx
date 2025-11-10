export default function App() {
  
  
  function Signup(formData) {
    const email = formData.get("email")
    console.log(email)

    const password = formData.get("password")
    console.log(password)
  }
  
  
  
  
    return (
    <section>
      <h1>Signup form</h1>
      <form action={Signup}>
        <label htmlFor="email">Email:</label>
        <input id="email" type="email" name="email" placeholder="joe@schmoe.com" />
        <br />
        
        <label htmlFor="password">Password:</label>
        <input id="password" type="password" name="password" placeholder="fmacnak" />
        
        <button type="submit">submit</button>
        
      </form>
    </section>
  )
}
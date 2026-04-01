"use client"; 
export default function Error({error, reset}: {error: Error, reset: () => void}) { 
  return (
    <div style={{padding: "2rem", fontFamily: "sans-serif", textAlign: "center"}}>
      <h2 style={{color: "#dc2626", marginBottom: "1rem"}}>Something went wrong!</h2>
      <button style={{padding: "0.5rem 1rem", backgroundColor: "#2563eb", color: "white", border: "none", borderRadius: "4px"}} onClick={() => reset()}>Try again</button>
    </div>
  ); 
}

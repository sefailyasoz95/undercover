import { useEffect, useState } from "react";

export function useRoute(): string {
  const [hash, setHash] = useState(window.location.hash);

  useEffect(() => {
    const update = () => {
      setHash(window.location.hash);
    };
    window.addEventListener("hashchange", update);
    return () => {
      window.removeEventListener("hashchange", update);
    };
  }, []);

  return hash;
}

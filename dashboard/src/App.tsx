import { ClaimView } from "./ClaimView";
import { Instructions } from "./Instructions";
import { Queue } from "./Queue";
import { useRoute } from "./useRoute";

function Page({ route }: Readonly<{ route: string }>) {
  const claimId = /^#\/claims\/(.+)$/.exec(route)?.[1];
  if (claimId) return <ClaimView claimId={claimId} />;
  if (route === "#/instructions") return <Instructions />;
  return <Queue />;
}

export function App() {
  const route = useRoute();

  return (
    <>
      <header className="masthead">
        <a className="brand" href="#/">
          UnderCover
        </a>
        <span className="tagline">Claims desk</span>
        <nav>
          <a
            href="#/"
            aria-current={
              route.startsWith("#/claims") || route === "#/instructions"
                ? undefined
                : "page"
            }
          >
            Queue
          </a>
          <a
            href="#/instructions"
            aria-current={route === "#/instructions" ? "page" : undefined}
          >
            Instructions
          </a>
        </nav>
      </header>
      <main>
        <Page route={route} />
      </main>
    </>
  );
}

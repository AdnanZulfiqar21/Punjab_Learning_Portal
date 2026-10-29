import { ButtonLink } from "@/components/button";
import { Icon } from "@/components/icons";
import { CenteredCard } from "@/components/learner-pages";

export default function NotFound() {
  return (
    <CenteredCard
      icon="compass"
      width="2xl"
      title="This page isn’t available"
      lead="The class, subject or chapter you asked for isn’t in the portal, or is no longer part of the current textbook catalogue. The portal currently covers Class 11 and Class 12 Biology, Chemistry, Physics and Computer Science."
    >
      <div className="flex flex-wrap justify-center gap-3">
        <ButtonLink href="/learn" size="lg">
          Browse all chapters
          <Icon name="arrow-right" size={18} />
        </ButtonLink>
        <ButtonLink href="/search" variant="secondary" size="lg">
          <Icon name="search" size={18} />
          Search a topic
        </ButtonLink>
      </div>
    </CenteredCard>
  );
}

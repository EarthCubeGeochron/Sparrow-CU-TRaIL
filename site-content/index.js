import { Markdown } from "@macrostrat/ui-components";
import aboutText from "./about.md";
import h from "@macrostrat/hyper";
import {
  PageGrainThumbnail,
  SampleCard,
  SampleLink,
  DataFileCard,
  DataFileLink,
} from "./grain-thumbnail";

export default {
  siteTitle: "CU TRaIL",
  shortSiteTitle: "TRaIL",
  landingText: h(Markdown, { src: aboutText }),
  sampleHeaderExt: PageGrainThumbnail,
  dataFileHeaderExt: PageGrainThumbnail,
  sampleCardContent: SampleCard,
  sampleLinkContent: SampleLink,
  dataFileLinkContent: DataFileLink,
  dataFileCardContent: DataFileCard,
};

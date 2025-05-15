import aboutText from "./about.md";
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
  landingText: aboutText,
  sampleHeaderExt: PageGrainThumbnail,
  dataFileHeaderExt: PageGrainThumbnail,
  sampleCardContent: SampleCard,
  sampleLinkContent: SampleLink,
  dataFileLinkContent: DataFileLink,
  dataFileCardContent: DataFileCard,
};

/**
 * Installs the generated catalogue. A separate module imported FIRST by ./index.ts: ES modules evaluate every import
 * before the importing module's own body, so procedure modules that check their tables at registration (defineCrud)
 * would otherwise run against an empty catalogue.
 */
import { installCatalogue, type Catalogue } from "./catalogue";
import { SCHEMA } from "../shared/schema.generated";

installCatalogue(SCHEMA as unknown as Catalogue);

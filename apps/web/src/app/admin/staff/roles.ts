// Staff role names as the owner reads them, and the roles that are limited to classes and subjects (P16.S4.T3).
export const ROLE_LABEL: Record<string, string> = {
  content_author: "Content author",
  subject_reviewer: "Subject reviewer",
  academic_adjudicator: "Academic adjudicator",
  publisher: "Publisher",
  support: "Support",
  finance: "Finance",
  platform_operator: "Platform operator",
  owner_admin: "Owner or administrator",
};

export const SCOPED_ROLES = new Set(["content_author", "subject_reviewer", "academic_adjudicator", "publisher"]);

// Parsing of an announcement .qmd into the fields used in the notification
// email.
//
// Kept in its own module, with no AWS SDK imports, so that CI can run this
// exact code against every announcement in the repository before any of them
// reaches S3. Testing a re-implementation would prove nothing: it is this
// function's behaviour that determines what subscribers receive.
//
// The whole `lambda/` directory is bundled by `lambda.Code.fromAsset('lambda')`
// in lib/backend-stack.ts, so this file is deployed alongside the handlers.

// Extract the title and short description from a post's YAML front matter.
// Throws when either is absent -- the caller must not send a malformed email.
function extractTitleAndContent(markdownContent) {
  const frontMatterMatch = markdownContent.match(/---([\s\S]*?)---/);
  if (!frontMatterMatch) {
    throw new Error('Invalid markdown format: Missing front matter');
  }
  const frontMatter = frontMatterMatch[1];

  const titleMatch = frontMatter.match(/title: ["']?([\s\S]*?)["']?(?=\n\S|$)/);
  if (!titleMatch) {
    throw new Error('Invalid markdown format: Missing title');
  }
  const title = titleMatch[1].trim();

  const descriptionMatch = frontMatter.match(/description:\s*(\|)?\s*([\s\S]*?)(?=\n\S|$)/);
  if (!descriptionMatch) {
    throw new Error('Invalid markdown format: Missing description');
  }
  const description = descriptionMatch[2].trim();

  return { title, description };
}

module.exports = { extractTitleAndContent };

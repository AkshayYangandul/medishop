import { useEffect } from 'react';

/**
 * Custom hook to dynamically set document page title
 */
export function useDocumentTitle(title) {
  useEffect(() => {
    const previousTitle = document.title;
    if (title) {
      document.title = `${title} | MediShop`;
    }
    return () => {
      document.title = previousTitle;
    };
  }, [title]);
}

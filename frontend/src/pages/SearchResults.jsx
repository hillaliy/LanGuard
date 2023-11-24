import BasePage from './BasePage';

const SearchResults = ({ searchTerm }) => {
  return (
    <>
      {searchTerm && (
        <>
          <h3 className="text-center mt-3 text-success">Search results</h3>
          <BasePage devices={searchTerm} />
        </>
      )}
    </>
  );
};

export default SearchResults;

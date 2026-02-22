import { Link } from 'react-router-dom';

const Navbar = () => {
  return (
    <nav className="bg-white shadow-md sticky top-0 z-50">
      <div className="container mx-auto px-4 py-4 flex justify-between items-center">
        <div className="text-2xl font-bold text-blue-600 tracking-tight">
          <Link to="/">MyStore</Link>
        </div>
        <ul className="hidden md:flex space-x-8 items-center font-medium">
          <li>
            <Link to="/" className="text-gray-700 hover:text-blue-600 transition-colors">Home</Link>
          </li>
          <li>
            <Link to="/products" className="text-gray-700 hover:text-blue-600 transition-colors">Products</Link>
          </li>
          <li>
            <Link to="/orders" className="text-gray-700 hover:text-blue-600 transition-colors">Orders</Link>
          </li>
        </ul>
        {/* Mobile menu toggle (simplified for now) */}
        <div className="md:hidden text-gray-700">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;

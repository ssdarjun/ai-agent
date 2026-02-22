import { Link } from 'react-router-dom';

function Home() {
  return (
    <div className="flex flex-col min-h-screen">
      {/* Hero Section */}
      <section className="relative bg-blue-900 text-white py-24 px-4 overflow-hidden">
        <div className="container mx-auto relative z-10">
          <div className="max-w-2xl">
            <h1 className="text-5xl md:text-6xl font-extrabold mb-6 leading-tight text-left">
              Elevate Your Lifestyle <br />
              <span className="text-blue-400">With Premium Gear</span>
            </h1>
            <p className="text-xl mb-10 text-blue-100 text-left">
              Explore our curated collection of high-quality products designed for the modern world. Style, comfort, and innovation delivered to your door.
            </p>
            <div className="flex space-x-4">
              <Link to="/products" className="bg-white text-blue-900 px-8 py-3 rounded-lg font-bold hover:bg-blue-50 transition-colors">
                Shop Now
              </Link>
              <button className="border-2 border-white text-white px-8 py-3 rounded-lg font-bold hover:bg-white hover:text-blue-900 transition-all">
                Learn More
              </button>
            </div>
          </div>
        </div>
        {/* Decorative elements */}
        <div className="absolute top-0 right-0 w-1/2 h-full bg-blue-800 transform skew-x-12 translate-x-1/4 hidden lg:block"></div>
      </section>

      {/* Categories Section */}
      <section className="py-20 bg-gray-50 px-4">
        <div className="container mx-auto">
          <h2 className="text-3xl font-bold mb-12 text-center text-gray-800">Shop by Category</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              { name: 'Electronics', img: 'https://images.unsplash.com/photo-1498049794561-7780e7231661?auto=format&fit=crop&q=80&w=400', color: 'bg-blue-100' },
              { name: 'Fashion', img: 'https://images.unsplash.com/photo-1445205170230-053b83016050?auto=format&fit=crop&q=80&w=400', color: 'bg-pink-100' },
              { name: 'Home & Living', img: 'https://images.unsplash.com/photo-1484101403033-57105d2b77ac?auto=format&fit=crop&q=80&w=400', color: 'bg-green-100' }
            ].map((cat) => (
              <div key={cat.name} className="group relative overflow-hidden rounded-2xl cursor-pointer">
                <img src={cat.img} alt={cat.name} className="w-full h-64 object-cover transform group-hover:scale-110 transition-transform duration-500" />
                <div className="absolute inset-0 bg-black/40 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                  <h3 className="text-white text-2xl font-bold">{cat.name}</h3>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Featured Products Intro */}
      <section className="py-20 px-4">
        <div className="container mx-auto flex flex-col md:flex-row items-center justify-between">
          <div className="md:w-1/2 mb-10 md:mb-0">
            <h2 className="text-4xl font-bold mb-6 text-gray-800 text-left">Quality Meets Innovation</h2>
            <p className="text-lg text-gray-600 mb-8 text-left leading-relaxed">
              We pride ourselves on offering only the best products. Every item in our store undergoes a rigorous selection process to ensure it meets our standards of excellence.
            </p>
            <ul className="space-y-4 mb-8 text-left">
              <li className="flex items-center space-x-3">
                <span className="bg-blue-100 text-blue-600 p-1 rounded-full">✓</span>
                <span className="text-gray-700">Premium Quality Materials</span>
              </li>
              <li className="flex items-center space-x-3">
                <span className="bg-blue-100 text-blue-600 p-1 rounded-full">✓</span>
                <span className="text-gray-700">Sustainable Manufacturing</span>
              </li>
              <li className="flex items-center space-x-3">
                <span className="bg-blue-100 text-blue-600 p-1 rounded-full">✓</span>
                <span className="text-gray-700">Exceptional Customer Support</span>
              </li>
            </ul>
            <Link to="/products" className="text-blue-600 font-bold hover:underline">
              View all products &rarr;
            </Link>
          </div>
          <div className="md:w-1/2 md:pl-12">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-blue-50 p-6 rounded-2xl mt-8">
                <div className="text-3xl mb-2">🚚</div>
                <h4 className="font-bold mb-1">Fast Shipping</h4>
                <p className="text-sm text-gray-600">Free delivery on orders over $100</p>
              </div>
              <div className="bg-gray-50 p-6 rounded-2xl">
                <div className="text-3xl mb-2">🛡️</div>
                <h4 className="font-bold mb-1">Secure Payments</h4>
                <p className="text-sm text-gray-600">Your data is safe with us</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Newsletter / CTA Section */}
      <section className="py-20 bg-blue-600 px-4">
        <div className="container mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold text-white mb-6">Ready to upgrade your style?</h2>
          <p className="text-blue-100 text-xl mb-10 max-w-2xl mx-auto">
            Join thousands of happy customers and start your shopping journey today.
          </p>
          <Link to="/products" className="bg-white text-blue-600 px-10 py-4 rounded-full font-bold text-lg hover:shadow-xl transition-all">
            Get Started Now
          </Link>
        </div>
      </section>
    </div>
  );
}

export default Home;

// Package calc provides calculator functions for LiveDoc demo.
package calc

// Add returns the sum of a and b.
func Add(a, b int) int {
	return a + b
}

// Subtract returns a minus b.
func Subtract(a, b int) int {
	return a - b
}

// Calculator holds state for chained operations.
type Calculator struct {
	value int
}

// Multiply multiplies x and y.
func (c *Calculator) Multiply(x, y int) int {
	c.value = x * y
	return c.value
}

// Divide returns a divided by b.
func (c Calculator) Divide(a, b int) int {
	return a / b
}

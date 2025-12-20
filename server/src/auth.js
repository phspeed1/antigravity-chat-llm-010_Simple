const express = require('express');
const passport = require('passport');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');
const { PrismaClient } = require('@prisma/client');

const prisma = new PrismaClient();
const router = express.Router();

// Trigger Google Login
router.get('/google', passport.authenticate('google', {
    scope: ['profile', 'email']
}));

// Callback
router.get('/google/callback',
    passport.authenticate('google', { failureRedirect: '/login-failed', session: false }), // session: false for JWT flow if we want pure JWT, but passport-google needs session for state usually. 
    // Actually, we can disable session if we don't use it, but state param might fail. 
    // However, since we set app.use(session), we can let passport use it for the flow, but NOT login the user into session permanently if we want stateless JWT.
    // The `passport.authenticate` above with `session: false` means it won't serialize user to session.
    (req, res) => {
        // User is available in req.user
        const token = jwt.sign(
            { id: req.user.id, email: req.user.email },
            process.env.SESSION_SECRET,
            { expiresIn: '1h' }
        );

        // Redirect to client with token
        // Use a more secure way in production (e.g. cookie), but for this task url param or cookie is fine.
        // Let's use a query param or a temporary cookie that client reads.
        // Easiest for "Simple" request: Redirect with token in URL (Fragment is better)
        res.redirect(`${process.env.CLIENT_URL}/auth-callback?token=${token}`);
    }
);

// Email/Password Signup
router.post('/signup', async (req, res) => {
    try {
        const { email, password, name } = req.body;

        // Check if user exists
        const existingUser = await prisma.user.findUnique({ where: { email } });
        if (existingUser) {
            return res.status(400).json({ error: 'User already exists' });
        }

        // Hash password
        const hashedPassword = await bcrypt.hash(password, 10);

        // Create user
        const user = await prisma.user.create({
            data: {
                email,
                password: hashedPassword,
                name
            }
        });

        // Issue Token
        const token = jwt.sign(
            { id: user.id, email: user.email },
            process.env.SESSION_SECRET,
            { expiresIn: '1h' }
        );

        res.json({ token, user });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

// Email/Password Login
router.post('/login', async (req, res) => {
    try {
        const { email, password } = req.body;

        const user = await prisma.user.findUnique({ where: { email } });
        if (!user) {
            return res.status(400).json({ error: 'Invalid credentials' });
        }

        if (!user.password) {
            return res.status(400).json({ error: 'Please login with Google' });
        }

        const isMatch = await bcrypt.compare(password, user.password);
        if (!isMatch) {
            return res.status(400).json({ error: 'Invalid credentials' });
        }

        const token = jwt.sign(
            { id: user.id, email: user.email },
            process.env.SESSION_SECRET,
            { expiresIn: '1h' }
        );

        res.json({ token, user });
    } catch (err) {
        console.error(err);
        res.status(500).json({ error: 'Server error' });
    }
});

router.get('/me', (req, res) => {
    // Middleware should check token
    // Implementing inline for simplicity first, or move to middleware
    const authHeader = req.headers.authorization;
    if (authHeader) {
        const token = authHeader.split(' ')[1];
        jwt.verify(token, process.env.SESSION_SECRET, (err, user) => {
            if (err) return res.sendStatus(403);
            res.json({ user });
        });
    } else {
        res.sendStatus(401);
    }
});

module.exports = router;
